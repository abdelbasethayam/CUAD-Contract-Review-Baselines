from backend.app.core.rag.confusion_pairs import resolve_confusion


def test_cap_vs_uncapped():
    text = "Each party's aggregate liability shall not exceed the fees paid in the prior twelve months."
    label, reason = resolve_confusion(
        text, "Uncapped Liability", candidates=["Cap On Liability", "Uncapped Liability"]
    )
    assert label == "Cap On Liability"
    assert reason


def test_noncompete_vs_exclusivity():
    text = "Distributor shall not compete with Supplier in the licensed territory for two years."
    label, reason = resolve_confusion(
        text, "Exclusivity", candidates=["Non-Compete", "Exclusivity"]
    )
    assert label == "Non-Compete"
