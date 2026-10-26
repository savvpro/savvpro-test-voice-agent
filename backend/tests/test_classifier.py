import pytest
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from app.nlu.classifier import IntentClassifier, to_features
from app.nlu.lexicon import load_intents
from app.nlu.normalizer import normalize
from app.nlu.train import RANDOM_STATE, TEST_SIZE, build_pipeline, load_dataset


def test_held_out_accuracy_at_least_85_percent():
    texts, labels = load_dataset()
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=TEST_SIZE, stratify=labels, random_state=RANDOM_STATE
    )
    model = build_pipeline().fit(x_train, y_train)
    assert accuracy_score(y_test, model.predict(x_test)) >= 0.85


def test_every_intent_has_at_least_25_utterances():
    for intent, utterances in load_intents().items():
        assert len(utterances) >= 25, intent


def test_training_data_is_all_strings():
    # YAML turns bare yes/no into booleans and 0300... into octal ints
    for utterances in load_intents().values():
        assert all(isinstance(u, str) for u in utterances)


def test_predict_returns_ranked_top_k(classifier):
    predictions = classifier.predict(normalize("I want to book an appointment"), top_k=3)
    assert len(predictions) == 3
    probabilities = [p for _, p in predictions]
    assert probabilities == sorted(probabilities, reverse=True)
    assert all(0.0 <= p <= 1.0 for p in probabilities)
    assert predictions[0][0] == "book_appointment"


def test_predict_empty_text(classifier):
    assert classifier.predict("") == []


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("cancle my apointment", "cancel_appointment"),  # STT misspellings
        ("re schedule my booking", "reschedule_appointment"),
        ("appointment chahiye", "book_appointment"),  # Urdu mix
        ("clinic kahan hai", "clinic_location"),
    ],
)
def test_robust_to_misspellings_and_urdu(classifier, text, intent):
    assert classifier.predict(normalize(text))[0][0] == intent


def test_entity_values_do_not_change_the_prediction(classifier):
    a = classifier.predict(normalize("does cardiology have anything on thursday"))[0]
    b = classifier.predict(normalize("does dermatology have anything on monday"))[0]
    assert a[0] == b[0] == "check_availability"
    assert to_features(normalize("cardiology on thursday")) == to_features(
        normalize("dermatology on monday")
    )


def test_trains_automatically_when_model_missing(tmp_path):
    path = tmp_path / "missing.joblib"
    model = IntentClassifier(path)
    assert not path.exists()
    assert model.predict("hello")[0][0] == "greet"
    assert path.exists()
