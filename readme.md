# Execute this

## XYFLOW Prototype

### Execute Backend
```
cd backend
python3 -m venv environment
source environment/bin/activate
pip install -r requirements.txt
uvicorn appv1:app --host 0.0.0.0 --port 5000 --reload
```

### Exxecute Frontend
```
npm install
npm start
```