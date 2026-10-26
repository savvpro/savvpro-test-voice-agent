# TableTalk — Design Document

## 1. Use Case

TableTalk is a restaurant reservation assistant that helps customers manage table bookings through a conversational interface.

The user can interact by typing messages or speaking through a microphone. The assistant interprets the request, checks the reservation rules, performs the relevant operation, and returns a response.

## 2. Main Use Cases

### 2.1 Create a Reservation

1. The user requests a new reservation.
2. The assistant asks for any missing information.
3. The user provides the reservation details.
4. The assistant validates the details.
5. The system checks whether a suitable table is available.
6. If a table is available, the reservation is created.
7. The assistant returns a reservation reference and confirmation.

### 2.2 View a Reservation

1. The user asks to view a reservation.
2. The assistant requests the reservation reference if needed.
3. The system searches its stored reservations.
4. The assistant displays the matching reservation details or explains that the reference was not found.

### 2.3 Update a Reservation

1. The user requests a change to an existing booking.
2. The assistant identifies the reservation.
3. The user provides the updated details.
4. The system validates the requested changes and checks availability when necessary.
5. If the update is valid, the reservation is modified.
6. The assistant confirms the result.

### 2.4 Cancel a Reservation

1. The user requests cancellation.
2. The assistant identifies the reservation.
3. The assistant asks the user to confirm the cancellation.
4. If the user confirms, the reservation is removed.
5. The assistant communicates the result.

If the user declines cancellation, the reservation remains unchanged.

## 3. System Architecture

The application has two main Python files.

### `main.py` — Assistant Logic

This file contains the reservation assistant and its decision-making logic, including:

- Processing user messages.
- Identifying supported intents.
- Managing conversation state.
- Collecting missing reservation information.
- Validating booking details.
- Checking table availability.
- Creating, updating, viewing, and cancelling reservations.
- Generating reservation references.
- Producing responses for the user.

### `ui.py` — User Interface

This file provides the Streamlit interface, including:

- Displaying conversation history.
- Accepting typed messages.
- Providing microphone input.
- Displaying reservation information.
- Presenting assistant responses.
- Supporting spoken output where browser functionality permits it.

## 4. How the Assistant Brain Makes Decisions

TableTalk uses a rule-based approach. It does not require a trained AI model to decide what action to perform.

The general processing flow is:

```text
User Input
    |
    v
Text or Voice Input Processing
    |
    v
Intent and Context Recognition
    |
    v
Conversation State and Required Details
    |
    v
Validation and Availability Checks
    |
    v
Reservation Operation
    |
    v
Assistant Response
```

### Step 1: Receive Input

The user enters a text message or provides speech through the interface. Voice input is converted into text before the reservation logic processes it.

### Step 2: Identify the Intent

The assistant examines the message for supported requests, such as making, viewing, updating, or cancelling a reservation.

Intent recognition uses programmed rules and keyword or phrase matching.

### Step 3: Check Conversation State

The assistant checks whether the conversation is already waiting for information, such as a reservation reference, date, time, party size, or cancellation confirmation.

This helps the assistant decide whether to continue an existing operation or begin a new one.

### Step 4: Collect Missing Details

If required information is missing, the assistant asks the user for it rather than attempting to complete the operation with incomplete details.

### Step 5: Validate the Request

The assistant checks the request against the application's booking rules, including supported booking times and valid reservation details.

### Step 6: Check Availability

The system checks whether an appropriate physical table is available for the requested time and date. A conflicting reservation prevents the same table from being assigned to overlapping bookings.

### Step 7: Perform the Operation

Depending on the intent and validation results, the assistant creates a reservation, retrieves a reservation, updates an existing booking, or cancels it after confirmation.

### Step 8: Respond to the User

The assistant returns a confirmation, requests missing information, or explains why the requested operation cannot be completed.

## 5. Reservation Rules

The current implementation is designed around eight physical tables and 30-minute booking intervals.

Booking start times are supported from noon through 11:30 PM, subject to the validation rules implemented in the code.

Each new reservation receives a reference number. Cancelled reservation references are not necessarily reused, which helps avoid confusion between old and new bookings.

## 6. Data Storage

Reservations are maintained in application memory.

This is suitable for a small demonstration but has limitations:

- Data may be lost when the application restarts.
- Reservations are not automatically shared across separate application processes.
- There is no persistent database backup.

A future version could use SQLite, PostgreSQL, or MongoDB for persistent storage.

## 7. Error Handling

The assistant should handle missing information, invalid booking details, unavailable tables, unknown reservation references, and declined cancellation requests with clear responses.

Validation and conversation-state handling help prevent incomplete or invalid reservation operations.

## 8. Design Limitations

The assistant follows programmed rules instead of using an LLM for open-ended reasoning. It may not understand requests that use phrases outside its supported patterns.

Its behavior is therefore dependent on the intent-matching rules, validation logic, and conversation-state implementation in `main.py`.
