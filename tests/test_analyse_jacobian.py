def test_correction_deduplication(tmp_path):
    import pandas as pd

    from scripts.analyse_jacobian import load_corrections

    rows = []

    for time_s in (1.0, 1.1, 1.2):
        rows.append({
            "elapsed_s": time_s,
            "controller_state": "SEARCH",
            "correction_iteration": 1,
            "correction_baseline_score": 2.0,
            "correction_predicted_score": 1.0,
            "correction_measured_score": 1.5,
            "correction_predicted_improvement": 1.0,
            "correction_actual_improvement": 0.5,
        })

    pd.DataFrame(rows).to_csv(
        tmp_path / "case_000.csv",
        index=False,
    )

    corrections = load_corrections(tmp_path)

    assert len(corrections) == 1
    assert corrections.iloc[0]["correction_iteration"] == 1
    assert corrections.iloc[0]["correction_actual_improvement"] == 0.5