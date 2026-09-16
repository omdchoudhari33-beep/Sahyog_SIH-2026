from app.mapping import severity_to_score, severity_to_urgency, track_to_ticket_value


def test_severity_to_score_known_values():
    assert severity_to_score("LOW") == 1.0
    assert severity_to_score("CRITICAL") == 4.0
    assert severity_to_score("low") == 1.0  # case-insensitive


def test_severity_to_score_unknown_defaults_low():
    assert severity_to_score("NOT_A_SEVERITY") == 1.0
    assert severity_to_score(None) == 1.0


def test_severity_to_urgency():
    assert severity_to_urgency("CRITICAL") == "high"
    assert severity_to_urgency("MEDIUM") == "medium"


def test_track_to_ticket_value():
    assert track_to_ticket_value("TRACK_A") == "track_a"
    assert track_to_ticket_value("TRACK_B") == "track_b"
    assert track_to_ticket_value("UNSURE") == "review_required"
    assert track_to_ticket_value(None) == "review_required"
