from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.nl2sql_agent import process_question, get_graph_image
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="NL2SQL E-Commerce Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],#any website can call API
    allow_methods=["*"],#GET, POST, PUT, DELETE allowed
    allow_headers=["*"],#any headers allowed
)

class QuestionRequest(BaseModel):
    question: str


class AnswerResponse(BaseModel):
    final_answer: str = ""
    query_generated: str = ""
    graph_json: str = ""



@app.post("/ask", response_model=AnswerResponse) #response_model: This defines the API response format:
def ask_question(req: QuestionRequest):
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    result = process_question(req.question)

    return AnswerResponse(
        final_answer=result.get("final_answer", "No answer generated."),
        query_generated=result.get("query_generated", ""),
        graph_json=result.get("graph_json", ""),
    )

@app.get("/workflow-image")
def workflow_image():
    png_data = get_graph_image()
    if png_data is None:
        raise HTTPException(status_code=500, detail="Could not generate graph image")
    return Response(content=png_data, media_type="image/png")


@app.get("/health")
def health():
    return {"status": "ok"}