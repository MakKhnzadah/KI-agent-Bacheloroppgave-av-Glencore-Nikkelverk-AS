from fastapi import FastAPI

app = FastAPI()
@app.get("/health")
def read_health():
    return {"status": "ok"}

@app.get("/kunskapsbank")
def read_kunskapsbank():
    return {"message": "Ermin tester kunskapsbank endpoint, ikke noe å tenke på her enda"}