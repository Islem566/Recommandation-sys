from fastapi import FastAPI, File, UploadFile,HTTPException
from pymongo import MongoClient
from bson import ObjectId
from pydantic import BaseModel
from typing import List
import re
import pandas as pd
import uuid
import json
import datetime
from fastapi.responses import JSONResponse

# FastAPI instance
app = FastAPI()

# Connexion à MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client["Test"]
mycollection = db["Catalogues"]
Transaction = db["Transaction"]

# Modèles Pydantic
class Option(BaseModel):
    _id: str
    option: str
    type: str
    code: str
    prix: str
    serviceClassEligible: str

# Insérer les options dans la collection "Catalogues"
@app.post("/Options")
async def insert_options():
     Options =[
        {"_id": "1", "option": "500 Mo", "type":"DATA","code": "opp1" , "prix" : "3900" , "serviceClassEligible":";1;2;3;4;9;10;"},
        {"_id": "2", "option": "8 Go" , "type": "DATA" , "code": "opp2" , "prix": "5800" , "serviceClassEligible":";1;2;3;4;5;9;10"},
        {"_id": "3", "option": "60 Min" , "type": "Voix", "code": "opp3" , "prix": "2000" , "serviceClassEligible":";1;2;4;5;9;10"},
        {"_id": "4", "option": "1000 SMS" , "type": "SMS", "code": "opp4" , "prix": "1000" , "serviceClassEligible":";1;2;3;5;9;10"},
        {"_id": "5", "option": " 90 Min" , "type": "Voix", "code": "opp5" , "prix": "5000" , "serviceClassEligible":";1;2;3;5;9;10"}
    ]
     mycollection.insert_many(Options)
     return {"message": "Data inserted successfully!"}

      
      

# Obtenir les options
@app.post("/getOptions/")
async def get_options(msisdn: int  , canal: str , num_options: int,file: UploadFile = File(...)):  
    global content
    global now
    global msisdn_id
    if msisdn is None:
        return JSONResponse(content={"error code": "1", "Error Message": "Not found"}, status_code=400)
   
    elif len(str(msisdn)) != 8 or not str(msisdn).isdigit(): 
        return JSONResponse(content={"error code" : "2", "ErrorMessage": "wrong format"}, status_code=400)
    
    if canal is None:
        return JSONResponse(content={"error code": "3", "Error Message": "Not found"}, status_code=400)
   
    elif canal not in ["ussd", "web"]:
        return JSONResponse(content={"Errorcode": "4" , "ErrorMessage": "Canal Not allowed" }, status_code=400)
   
    
    elif num_options < 1:
        num_options = 1
    
    contents = await file.read()
    body = json.loads(contents)
    expiryDate = False
    ServiceCurrent= False
    for d in body:

     if "supervisionExpiryDate" in d and d["supervisionExpiryDate"] is not None:
        expiryDate = True

        if datetime.datetime.strptime(d['supervisionExpiryDate'][:-6],'%Y%m%dT%H:%M:%S') < datetime.datetime.today():

             return JSONResponse(content={"expiration date": d['supervisionExpiryDate'], "message": " msisdn expired"}, status_code=400)
     if not expiryDate:
         return JSONResponse(content={"ErrorMessage": "supervisionExpiryDate Not found"}, status_code=400)
      
     if "serviceClassCurrent" in d and d["serviceClassCurrent"] is not None:
        ServiceCurrent= True

    if not ServiceCurrent:
        return JSONResponse(content={"ErrorMessage": "serviceClassCurrent Not found"}, status_code=400)
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
    unique_id = "{}-{}".format(timestamp, uuid.uuid4().hex[:4])
    now = datetime.datetime.now()
   
    service_class_current = body[0]["serviceClassCurrent"]
    result = ";" + service_class_current +";"
    db.Catalogues.find({"serviceClassEligible": re.compile(result)})
#condition
    account_dict = None
    for item in body:
      if "AccountValue" in item:
           account_dict = item
           break


    if account_dict is None:
        return JSONResponse( content= {"No Dectionnay element with accountvalue found in data"}, status_code=400)


    res = db.Catalogues.find({"prix": {"$lte": account_dict["AccountValue"]}},{"serviceClassEligible": 0})

    code_options = db.Catalogues.find_one(
    {"prix": {"$lte": account_dict["AccountValue"]}},
     { "code": 1 });
   

    if code_options:
      code = code_options["code"]
      print(code)
    options = []
    for option in res:
        options.append(option)
    if not options:
        raise HTTPException(status_code=404, detail="Aucune option disponible")
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    now = datetime.datetime.now()
    unique_id= "{}-{}".format(timestamp, uuid.uuid4().hex[:4])
    codeOptions = [option["code"] for option in options]
    print(codeOptions)
    suggeste_option = ";".join(codeOptions)
    

    Transaction={"_id": unique_id, "datetime": now , "msisdn" : msisdn , "canal": canal , "serviceClassEligible": service_class_current, "MainAccount":account_dict["AccountValue"] ,"suggeste_options": suggeste_option}

    db.Transaction.insert_one(Transaction)
   
    timestampSuffix  = str(datetime.datetime.now()).split(":")[0].replace(" ", "-")
    print(timestampSuffix)
    timestampEdr= str(datetime.datetime.now()).split(".")[0]

    data = {"TimeStampEdr": [timestampEdr], "msisdn": [msisdn], "canal": [canal] ,"serviceClassEligible": [service_class_current],"MainAccount":account_dict["AccountValue"], "transaction_id": unique_id,"code_option": code , "Errorcode":'9', "ErrorMessage":'succes'}

    df = pd.DataFrame(data)
    df.to_csv("/home/islem/Option Boost/mon_environnement/test-"+timestampSuffix+".edr", mode="a", index=False, header=False)
    print(df.head())

    return options
    
     
@app.get("/status/{transaction_id}")
async def status(transaction_id: str):
     collections= db["Transaction"]
     
     Document = collections.find({"_id":transaction_id})
     
     if Document:
        datetime_Status= str(datetime.datetime.now())
        print(datetime_Status)

        collections.update_one(
            {"_id": transaction_id},
            {"$set": {"optionStatus": "ok" , "Current_datetime":datetime_Status}}
        )
        return {"message": "Option status updated successfully."}
     else:
         return{"Message":"Document Not Found"}
