import fitz
from src.agents.agents.guardrail_agent import guardrail_agent
import asyncio

test_cases = [
    {"path": "data/safe1.pdf", "is_safe": True},
    {"path": "data/safe2.pdf", "is_safe": True},
    {"path": "data/bad1.pdf", "is_safe": False},
    {"path": "data/bad2.pdf", "is_safe": False},
    {"path": "data/bad3.pdf", "is_safe": False},
]

@pytest.mark.asyncio
def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    return "".join([page.get_text() for page in doc])


async def test_guardrail(extract_text):
    agent=guardrail_agent()
    TP=FP=FN=TN=0

    for case in test_cases:
        pdf_path=case["path"]
        expected = case["is_safe"]

        text = extract_text(pdf_path)

        state = {
            "pdf_path": pdf_path,
            "waybill_text": text,
            "error_log": []
        }

        result = await agent.check_security(state)
        predicted = result["is_safe"]

        # ---- confusion matrix ----
        if not expected and not predicted:
            TP += 1
        elif expected and not predicted:
            FP += 1
        elif not expected and predicted:
            FN += 1
        elif expected and predicted:
            TN += 1

    # ---- metrics ----
    total = TP + TN + FP + FN

    accuracy = (TP + TN) / total if total else 0
    precision = TP / (TP + FP) if (TP + FP) else 0
    recall = TP / (TP + FN) if (TP + FN) else 0

    print("\n--- Guardrail Metrics ---")
    print(f"TP: {TP}, FP: {FP}, FN: {FN}, TN: {TN}")
    print(f"Accuracy: {accuracy:.2f}")
    print(f"Precision: {precision:.2f}")
    print(f"Recall: {recall:.2f}")

    # basic assertion (you can tune later)
    assert recall >= 0.7, "Guardrail is missing too many unsafe documents"




