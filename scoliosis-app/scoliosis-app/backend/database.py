from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import json
import asyncio
from bson import ObjectId

load_dotenv()

# =================================================================================
# 📂 LOCAL DATABASE FALLBACK ENGINE (NO MONGODB INSTALLED REQUIRED)
# =================================================================================
class MockCollection:
    def __init__(self, filename, seed_data=None):
        self.filename = filename
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as f:
                json.dump(seed_data or [], f, indent=2)

    def _read_data(self):
        try:
            with open(self.filename, 'r') as f:
                data = json.load(f)
                for item in data:
                    if '_id' in item and isinstance(item['_id'], str):
                        try:
                            item['_id'] = ObjectId(item['_id'])
                        except Exception:
                            pass
                return data
        except Exception:
            return []

    def _write_data(self, data):
        serialized = []
        for item in data:
            copy_item = item.copy()
            if '_id' in copy_item:
                copy_item['_id'] = str(copy_item['_id'])
            serialized.append(copy_item)
        with open(self.filename, 'w') as f:
            json.dump(serialized, f, indent=2)

    async def find(self, query=None):
        class AsyncCursor:
            def __init__(self, items):
                self.items = items
                self.index = 0
            def __aiter__(self):
                return self
            async def __anext__(self):
                if self.index < len(self.items):
                    val = self.items[self.index]
                    self.index += 1
                    return val
                else:
                    raise StopAsyncIteration
        items = self._read_data()
        if query:
            filtered = []
            for item in items:
                match = True
                for k, v in query.items():
                    if item.get(k) != v:
                        match = False
                        break
                if match:
                    filtered.append(item)
            return AsyncCursor(filtered)
        return AsyncCursor(items)

    async def find_one(self, query, sort=None):
        items = self._read_data()
        if sort and sort[0][0] == 'timestamp':
            items = sorted(items, key=lambda x: x.get('timestamp', ''), reverse=True)
        for item in items:
            match = True
            for k, v in query.items():
                if item.get(k) != v:
                    match = False
                    break
            if match:
                return item
        return None

    async def insert_one(self, item):
        items = self._read_data()
        if '_id' not in item:
            item['_id'] = ObjectId()
        items.append(item)
        self._write_data(items)
        class InsertResult:
            def __init__(self, inserted_id):
                self.inserted_id = inserted_id
        return InsertResult(item['_id'])

    async def update_one(self, query, update):
        items = self._read_data()
        modified = 0
        for item in items:
            match = True
            for k, v in query.items():
                if item.get(k) != v:
                    match = False
                    break
            if match:
                if '$set' in update:
                    for k, v in update['$set'].items():
                        item[k] = v
                if '$push' in update:
                    for k, v in update['$push'].items():
                        if k not in item:
                            item[k] = []
                        item[k].append(v)
                modified += 1
                break
        if modified > 0:
            self._write_data(items)
        class UpdateResult:
            def __init__(self, modified_count):
                self.modified_count = modified_count
        return UpdateResult(modified)

    async def delete_one(self, query):
        items = self._read_data()
        initial_len = len(items)
        items = [item for item in items if not all(item.get(k) == v for k, v in query.items())]
        deleted = initial_len - len(items)
        if deleted > 0:
            self._write_data(items)
        class DeleteResult:
            def __init__(self, deleted_count):
                self.deleted_count = deleted_count
        return DeleteResult(deleted)


# =================================================================================
# 🔗 SMART COLLECTION WRAPPER (FALLS BACK ON CONNECTION TIMEOUT)
# =================================================================================
class CursorWrapper:
    def __init__(self, mongo_cursor, fallback_loader):
        self.mongo_cursor = mongo_cursor
        self.fallback_loader = fallback_loader
        self.cursor = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.cursor is None:
            if self.mongo_cursor is not None:
                try:
                    self.cursor = self.mongo_cursor
                except Exception:
                    self.cursor = await self.fallback_loader()
            else:
                self.cursor = await self.fallback_loader()
        try:
            return await self.cursor.__anext__()
        except StopAsyncIteration:
            raise StopAsyncIteration
        except Exception:
            self.cursor = await self.fallback_loader()
            return await self.cursor.__anext__()


class SmartCollectionWrapper:
    def __init__(self, mongo_collection, fallback_filename, seed_data=None):
        self.mongo_collection = mongo_collection
        self.fallback = MockCollection(fallback_filename, seed_data)
        self.use_fallback = False

    async def _execute(self, method_name, *args, **kwargs):
        if self.use_fallback:
            method = getattr(self.fallback, method_name)
            return await method(*args, **kwargs)
        try:
            method = getattr(self.mongo_collection, method_name)
            res = method(*args, **kwargs)
            return await res
        except Exception as e:
            print(f"⚠️ MongoDB operation failed: {e}. Switching to local JSON storage!")
            self.use_fallback = True
            method = getattr(self.fallback, method_name)
            return await method(*args, **kwargs)

    async def find_one(self, query, sort=None):
        return await self._execute('find_one', query, sort=sort)

    async def insert_one(self, item):
        return await self._execute('insert_one', item)

    async def update_one(self, query, update):
        return await self._execute('update_one', query, update)

    async def delete_one(self, query):
        return await self._execute('delete_one', query)

    def find(self, query=None):
        if self.use_fallback:
            async def get_fallback_cursor():
                return await self.fallback.find(query)
            return CursorWrapper(None, get_fallback_cursor)

        try:
            mongo_cursor = self.mongo_collection.find(query)
        except Exception:
            self.use_fallback = True
            mongo_cursor = None

        async def get_fallback_cursor():
            self.use_fallback = True
            return await self.fallback.find(query)

        return CursorWrapper(mongo_cursor, get_fallback_cursor)


# =================================================================================
# 🧬 SEED CLINICAL DATA SETS
# =================================================================================
seed_patients = [
    {
        "_id": "60c72b2f9b1d8b2a3c8e4d56",
        "firstName": "Ahmet",
        "lastName": "Yilmaz",
        "dateOfBirth": "2012-05-15",
        "gender": "Male",
        "diagnosisType": "Adolescent Idiopathic",
        "curveLocation": "Thoracic (Right)",
        "rissersSign": 2,
        "initialCobbAngle": 18.5,
        "treatmentPlan": "Bracing & Physical Therapy",
        "braceType": "Boston Brace",
        "braceHoursPerDay": 18,
        "physicalTherapy": True,
        "visits": [
            {
                "visitDate": "2025-09-10",
                "cobbAngle": 18.5,
                "spineRegion": "Thoracic",
                "progression": 0.0,
                "physician": "Dr. Onur Tekin",
                "notes": "Initial diagnosis. Boston brace prescribed.",
                "painLevel": 2
            },
            {
                "visitDate": "2026-03-12",
                "cobbAngle": 16.2,
                "spineRegion": "Thoracic",
                "progression": -2.3,
                "physician": "Dr. Onur Tekin",
                "notes": "Brace compliance is excellent. Curve shows mild correction.",
                "painLevel": 1
            }
        ]
    }
]

# =================================================================================
# 🔌 INITIALIZE CONNECTORS
# =================================================================================
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
print(f"📡 Attempting MongoDB initialization at: {mongo_uri}")

# Set a fast 1500ms timeout for connection select
client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=1500)
db = client.scoliosisDB

mongo_patients = db.get_collection("patients")
mongo_telemetry = db.get_collection("telemetry")

patients_collection = SmartCollectionWrapper(mongo_patients, "patients_local_db.json", seed_patients)
telemetry_collection = SmartCollectionWrapper(mongo_telemetry, "telemetry_local_db.json")