from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv

from app.core.rag_runtime import get_rag_service

# ROOT = Path(__file__).resolve().parents[3]
# load_dotenv(dotenv_path=ROOT / ".env", override=True)

load_dotenv()
def format_recent_history(messages: List[Dict], max_messages: int = 6) -> str:
    recent = messages[-max_messages:] if messages else []
    lines = []

    for msg in recent:
        role = msg.get("role", "user")
        content = msg.get("content", "").strip()
        if not content:
            continue

        speaker = "Utilisateur" if role == "user" else "Assistant"
        lines.append(f"{speaker}: {content}")

    return "\n".join(lines)


def build_standalone_question(question: str, history_text: str) -> str:
    """
    Version simple : si historique vide, on renvoie la question telle quelle.
    Sinon, on enrichit la question avec le contexte conversationnel.
    """
    if not history_text.strip():
        return question.strip()

    return (
        "En tenant compte de l'historique suivant, reformule la dernière question "
        "en une question autonome et claire.\n\n"
        f"Historique:\n{history_text}\n\n"
        f"Dernière question:\n{question.strip()}\n\n"
        "Question reformulée:"
    )


def build_answer_prompt(
    original_question: str,
    standalone_question: str,
    history_text: str,
) -> str:
    """
    On fabrique une question enrichie pour que le RAG réponde mieux
    en tenant compte du contexte conversationnel.
    """
    return f"""
Tu réponds à une question utilisateur dans un contexte conversationnel.

Historique récent :
{history_text if history_text.strip() else "Aucun historique"}

Question originale :
{original_question}

Question reformulée :
{standalone_question}

Réponds de manière claire, utile et structurée, en tenant compte du contexte.
""".strip()


def conversational_rag_answer(
    question: str,
    conversation_messages: List[Dict],
    top_k: int = 5,
) -> Dict:
    rag = get_rag_service()

    history_text = format_recent_history(conversation_messages, max_messages=6)

    standalone_rewrite_prompt = build_standalone_question(question, history_text)

    # Étape 1 : reformulation via ton RAG existant si besoin simple
    # Ici on reste pragmatique : si l’historique existe, on envoie une question enrichie.
    # Si plus tard tu veux, on pourra faire une vraie étape de reformulation séparée.
    standalone_question = question.strip()

    if history_text.strip():
        # version simple et robuste :
        standalone_question = (
            f"Historique récent:\n{history_text}\n\n"
            f"Question actuelle:\n{question.strip()}\n\n"
            "Réécris implicitement la question pour qu'elle soit autonome."
        )

    # Étape 2 : retrieval + génération avec la question contextualisée
    rag_input = build_answer_prompt(
        original_question=question.strip(),
        standalone_question=standalone_question,
        history_text=history_text,
    )

    result = rag.answer(rag_input, top_k=top_k)

    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "standalone_question": standalone_question,
        "history_used": history_text,
    }