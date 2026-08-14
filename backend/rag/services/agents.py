"""The 6 required agents (cahier des charges §5), implemented as a lightweight
Agent/Task pattern (role, goal, backstory + a callable) rather than the
`crewai` package — that package requires Python <3.14 and this environment
runs 3.14, so its dependency chain (pinned old numpy) cannot install here.
The orchestrateur/RAG/pédagogique agents below are fully functional; the
générateur/évaluation/notification agents are declared with their real
persona but only expose a stub `run()` for now (implemented in later phases).
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from django.conf import settings

from .llm import complete, stream_complete
from .retrieval import retrieve_chunks

logger = logging.getLogger(__name__)


@dataclass
class Agent:
    key: str
    role: str
    goal: str
    backstory: str
    run: Optional[Callable] = field(default=None, repr=False)


VALID_INTENTS = [
    "question_factuelle",
    "explication",
    "demande_de_quiz",
    "demande_de_resume",
    "autre",
]


# --- 1. Orchestrateur ------------------------------------------------------

def _run_orchestrateur(conversation_history, user_message):
    history_text = "\n".join(
        f"{'Apprenant' if m['role'] == 'USER' else 'Assistant'}: {m['content']}"
        for m in conversation_history
    )
    system_prompt = (
        "Tu es l'agent orchestrateur d'une plateforme EdTech RAG. Ton rôle est de "
        "classifier l'intention de la question d'un apprenant et de la reformuler "
        "en une requête de recherche autonome (en résolvant les pronoms/ellipses "
        "grâce à l'historique de conversation).\n\n"
        f"Intentions possibles (choisis exactement une valeur) : {', '.join(VALID_INTENTS)}.\n"
        "- question_factuelle : une question précise avec une réponse factuelle attendue.\n"
        "- explication : une demande d'explication ou d'approfondissement d'un concept.\n"
        "- demande_de_quiz : l'apprenant veut être testé / veut un quiz.\n"
        "- demande_de_resume : l'apprenant veut un résumé ou une fiche de synthèse.\n"
        "- autre : ne correspond à aucune des catégories ci-dessus.\n\n"
        "Réponds STRICTEMENT en JSON, sans texte autour, au format :\n"
        '{"intent": "...", "enriched_query": "..."}'
    )
    user_prompt = f"Historique récent:\n{history_text or '(aucun)'}\n\nNouveau message: {user_message}"

    raw = complete(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=settings.GEMINI_ORCHESTRATOR_MODEL,
        temperature=0,
        max_tokens=300,
    )

    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        parsed = json.loads(raw[start:end])
        intent = parsed.get("intent") if parsed.get("intent") in VALID_INTENTS else "autre"
        enriched_query = parsed.get("enriched_query") or user_message
        return {"intent": intent, "enriched_query": enriched_query}
    except Exception:
        logger.warning("Orchestrateur: could not parse LLM output, falling back. raw=%r", raw)
        return {"intent": "autre", "enriched_query": user_message}


orchestrateur = Agent(
    key="orchestrateur",
    role="Orchestrateur",
    goal="Classifier l'intention de l'apprenant et enrichir sa requête avec la mémoire conversationnelle.",
    backstory=(
        "Un routeur pédagogique expérimenté qui comprend rapidement ce que veut "
        "un apprenant et reformule sa question pour la recherche documentaire."
    ),
    run=_run_orchestrateur,
)


# --- 2. Agent RAG ------------------------------------------------------

def _run_rag(owner_id, document_ids, enriched_query, top_k=None):
    return retrieve_chunks(owner_id, document_ids, enriched_query, top_k=top_k)


agent_rag = Agent(
    key="rag",
    role="Agent RAG",
    goal="Retrouver les passages les plus pertinents dans les documents de l'apprenant.",
    backstory=(
        "Un documentaliste méthodique qui interroge la base vectorielle Chroma "
        "et construit le contexte le plus utile pour répondre."
    ),
    run=_run_rag,
)


# --- 3. Agent pédagogique ------------------------------------------------------

LEVEL_INSTRUCTIONS = {
    "SIMPLE": "Explique comme à un débutant complet, avec des mots simples et des analogies concrètes.",
    "INTERMEDIATE": "Explique à un niveau intermédiaire, avec le vocabulaire technique courant du domaine.",
    "EXPERT": "Explique à un niveau expert, sois précis et concis, n'hésite pas à utiliser un vocabulaire technique avancé.",
}


def _build_pedagogique_messages(conversation_history, chunks, enriched_query, intent, level):
    context_blocks = "\n\n".join(
        f"[{i + 1}] (page {c['page_number']}) {c['text']}" for i, c in enumerate(chunks)
    )
    level_instruction = LEVEL_INSTRUCTIONS.get(level, LEVEL_INSTRUCTIONS["INTERMEDIATE"])

    system_prompt = (
        "Tu es l'agent pédagogique d'une plateforme EdTech RAG. Tu réponds aux questions "
        "des apprenants EXCLUSIVEMENT à partir des passages fournis ci-dessous, extraits de "
        "leurs propres documents. Si les passages ne permettent pas de répondre, dis-le "
        "clairement plutôt que d'inventer une réponse (pour éviter les hallucinations).\n\n"
        f"{level_instruction}\n\n"
        "Cite tes sources avec des numéros entre crochets correspondant EXACTEMENT aux "
        "passages ci-dessous, par exemple [1] ou [2][3]. N'invente jamais de numéro de "
        "citation qui ne correspond à aucun passage.\n\n"
        f"Passages disponibles:\n{context_blocks or '(aucun passage trouvé)'}"
    )

    if intent == "demande_de_quiz":
        system_prompt += (
            "\n\nNote: l'apprenant demande un quiz. La génération de quiz interactifs "
            "complets n'est pas encore disponible sur cette version — réponds à sa "
            "question du mieux possible à partir des passages, et précise brièvement "
            "que la génération de quiz arrive dans une prochaine mise à jour."
        )

    messages = [{"role": "system", "content": system_prompt}]
    for m in conversation_history[-6:]:
        messages.append(
            {"role": "user" if m["role"] == "USER" else "assistant", "content": m["content"]}
        )
    messages.append({"role": "user", "content": enriched_query})
    return messages


def _stream_pedagogique(conversation_history, chunks, enriched_query, intent, level):
    messages = _build_pedagogique_messages(conversation_history, chunks, enriched_query, intent, level)
    yield from stream_complete(messages, model=settings.GEMINI_PEDAGOGICAL_MODEL)


agent_pedagogique = Agent(
    key="pedagogique",
    role="Agent pédagogique",
    goal="Rédiger une réponse pédagogique, sourcée et adaptée au niveau de l'apprenant.",
    backstory=(
        "Un tuteur patient qui explique clairement, ne s'écarte jamais des documents "
        "fournis et cite systématiquement ses sources."
    ),
    run=_stream_pedagogique,
)


# --- 4, 5, 6. Stub agents (implemented in later phases) ------------------------------------------------------

def _not_implemented_stub(agent_key):
    def _run(*args, **kwargs):
        return {
            "status": "not_implemented",
            "agent": agent_key,
            "message": f"L'agent {agent_key} sera implémenté dans une prochaine phase.",
        }

    return _run


agent_generateur = Agent(
    key="generateur",
    role="Agent générateur",
    goal="Générer des questions de quiz (QCM, Vrai/Faux, questions ouvertes) à partir des documents.",
    backstory="Un concepteur pédagogique qui transforme le contenu des documents en exercices évaluables.",
    run=_not_implemented_stub("generateur"),
)

agent_evaluation = Agent(
    key="evaluation",
    role="Agent d'évaluation",
    goal="Corriger les réponses aux quiz (exact match ou évaluation sémantique assistée par LLM).",
    backstory="Un correcteur rigoureux qui note avec des explications sourcées.",
    run=_not_implemented_stub("evaluation"),
)

agent_notification = Agent(
    key="notification",
    role="Agent de notification",
    goal="Générer et envoyer des e-mails personnalisés aux apprenants.",
    backstory="Un chargé de communication qui rédige des e-mails clairs et pertinents.",
    run=_not_implemented_stub("notification"),
)


ALL_AGENTS = {
    a.key: a
    for a in [
        orchestrateur,
        agent_rag,
        agent_pedagogique,
        agent_generateur,
        agent_evaluation,
        agent_notification,
    ]
}
