from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from models import Patient, Visit, TelemetryData
from database import patients_collection, telemetry_collection
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
import base64

load_dotenv()
app = FastAPI(title="Scoliosis Clinic API", version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid record identifier format: '{id_str}'"
        )

@app.get("/api/patients")
async def get_patients():
    patients = []
    async for p in patients_collection.find():
        p["_id"] = str(p["_id"])
        patients.append(p)
    return patients

@app.get("/api/patients/{id}")
async def get_patient(id: str):
    obj_id = verify_object_id(id)
    patient = await patients_collection.find_one({"_id": obj_id})
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient record not found"
        )
    patient["_id"] = str(patient["_id"])
    return patient

@app.post("/api/patients")
async def add_patient(patient: Patient):
    patient_data = patient.model_dump() if hasattr(patient, "model_dump") else patient.dict()
    result = await patients_collection.insert_one(patient_data)
    return {"id": str(result.inserted_id)}

@app.post("/api/patients/{id}/visits")
async def add_visit(id: str, visit: Visit):
    obj_id = verify_object_id(id)
    patient = await patients_collection.find_one({"_id": obj_id})
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )

    visit_data = visit.model_dump() if hasattr(visit, "model_dump") else visit.dict()
    await patients_collection.update_one(
        {"_id": obj_id},
        {"$push": {"visits": visit_data}}
    )
    return {"message": "Visit successfully registered"}

@app.put("/api/patients/{id}")
async def update_patient(id: str, patient: Patient):
    obj_id = verify_object_id(id)
    exists = await patients_collection.find_one({"_id": obj_id})
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
        
    data = patient.model_dump() if hasattr(patient, "model_dump") else patient.dict()
    await patients_collection.update_one(
        {"_id": obj_id},
        {"$set": data}
    )
    return {"message": "Patient records successfully updated"}

@app.delete("/api/patients/{id}")
async def delete_patient(id: str):
    obj_id = verify_object_id(id)
    result = await patients_collection.delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    return {"message": "Patient successfully purged"}

@app.post("/api/patients/{id}/photo")
async def upload_photo(id: str, file: UploadFile = File(...)):
    obj_id = verify_object_id(id)
    exists = await patients_collection.find_one({"_id": obj_id})
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
        
    max_size = 5 * 1024 * 1024
    contents = await file.read(max_size + 1)
    if len(contents) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 5MB safety limit"
        )
        
    encoded = base64.b64encode(contents).decode("utf-8")
    mime = file.content_type
    photo_data = f"data:{mime};base64,{encoded}"
    
    await patients_collection.update_one(
        {"_id": obj_id},
        {"$set": {"photo": photo_data}}
    )
    return {"message": "Photo uploaded successfully"}

@app.post("/api/telemetry")
async def save_telemetry(data: TelemetryData):
    from datetime import datetime
    telemetry_data = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    telemetry_data["timestamp"] = datetime.utcnow().isoformat()
    
    result = await telemetry_collection.insert_one(telemetry_data)
    return {"id": str(result.inserted_id), "status": "Telemetry successfully logged"}

@app.get("/api/telemetry/{patient_id}/latest")
async def get_latest_telemetry(patient_id: str):
    latest = await telemetry_collection.find_one(
        {"patient_id": patient_id},
        sort=[("timestamp", -1)]
    )
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry data found for patient ID: '{patient_id}'"
        )
    latest["_id"] = str(latest["_id"])
    return latest