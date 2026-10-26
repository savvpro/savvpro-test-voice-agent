# TableTalk — Voice Reservation Assistant

## 1. Project Overview

TableTalk is a rule-based restaurant reservation assistant developed using Python and Streamlit. It allows users to create, view, update, and cancel restaurant reservations through a conversational interface.

Users can type their requests or use voice input. The assistant processes requests, validates booking details, checks table availability, and responds with appropriate messages.

## 2. Features

- Create restaurant reservations.
- Check table availability for a requested date and time.
- View existing reservations.
- Update reservation details.
- Cancel reservations with user confirmation.
- Accept typed input and microphone-based voice input.
- Provide spoken responses through browser text-to-speech.
- Generate unique reservation reference numbers.
- Run automated unit tests using Python's built-in `unittest` framework.

## 3. Technologies Used

- **Python** — reservation logic and request processing.
- **Streamlit** — web-based user interface.
- **streamlit-mic-recorder** — microphone input.
- **Browser Speech Synthesis** — spoken assistant responses.
- **unittest** — automated testing of reservation logic.

## 4. Project Structure

```text
TableTalk/
├── main.py
├── ui.py
├── test.py
├── README.md
├── DESIGN.md
└── AI_USAGE.md
```

- `main.py` — contains the reservation assistant's logic.
- `ui.py` — provides the Streamlit user interface.
- `test.py` — contains automated unit tests.
- `README.md` — explains installation and usage.
- `DESIGN.md` — describes the system design and decision-making process.
- `AI_USAGE.md` — documents AI-assisted development.

## 5. Requirements

Install Python and open a terminal in the project directory.

Install the required packages:

```bash
pip install streamlit streamlit-mic-recorder
```

If a `requirements.txt` file is available, you can install dependencies with:

```bash
pip install -r requirements.txt
```

## 6. How to Run the Application

Run the application using the command supported by your project configuration.

Option 1:

```bash
python main.py
```

Option 2:

```bash
python -m streamlit run ui.py
```

Open the local URL displayed in the terminal, usually:

`http://localhost:8501`

## 7. How to Use TableTalk

1. Open the application in your browser.
2. Type a reservation request or use the microphone input.
3. Provide the requested details, such as your name, reservation date, time, and party size.
4. Follow the assistant's prompts to complete the reservation.
5. Keep the reservation reference provided by the assistant.
6. Use the conversation to view, update, or cancel an existing reservation.

## 8. Automated Testing

The project includes `test.py`, which uses Python's built-in `unittest` framework to test selected reservation assistant functionality.

### Run the tests

Open the terminal in the project directory and execute:

```bash
python test.py
```

The test script reports which tests pass or fail.

### Current test coverage

The tests are intended to cover:

- Parsing times in AM/PM format.
- Parsing times in 24-hour format.
- Handling invalid time input.
- Creating a reservation.
- Generating unique reservation references.
- Checking the configured number of physical tables.
- Verifying the configured booking duration.

The tests depend on the methods and attributes implemented in `main.py`. Update the tests if the implementation changes.

## 9. Reservation Rules

The current implementation is designed around:

- Eight physical tables.
- 30-minute booking intervals.
- Booking start times from noon through 11:30 PM, subject to the validation rules in the code.
- Unique reservation references for new bookings.

Cancelled reservation references are not necessarily reused.

## 10. Data Storage and Limitations

Reservations are stored in application memory. As a result:

- Reservations may be lost when the application process restarts.
- The application does not provide persistent database storage.
- Voice input depends on microphone and browser support.
- Spoken responses depend on browser speech-synthesis support.
- The assistant uses programmed rules rather than a trained language model to interpret requests.

## 11. Future Improvements

- Add database storage using SQLite, PostgreSQL, or MongoDB.
- Expand automated test coverage.
- Improve natural-language intent recognition.
- Strengthen input validation and error handling.
- Deploy the application for online access.
