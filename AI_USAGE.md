# TableTalk — AI Tools and Usage Report

## 1. AI Tool Used

### ChatGPT by OpenAI — Free Version

The free version of ChatGPT was used as an AI-assisted tool during the development of TableTalk.

## 2. How AI Helped

ChatGPT was used to assist with the following development tasks:

- Reviewing and improving Python code.
- Identifying and debugging conversation-state issues.
- Improving the reservation assistant's conversational flow.
- Refining reservation cancellation confirmation messages.
- Suggesting solutions for handling user requests and reservation references.

All suggested changes should be reviewed and tested to ensure that they work correctly in the application.

## 3. Errors and Debugging

During development, a conversation-state issue was identified in which the assistant could continue asking for a reservation reference even when the user wanted to start a new booking.

ChatGPT helped suggest improvements so the assistant could recognize a new-booking request and move away from the previous pending operation.

The following scenarios should be tested:

1. Start a reservation operation.
2. Enter an invalid or cancelled reservation reference.
3. Request a new booking.
4. Verify that the assistant responds to the new booking request.
5. Test invalid booking details, unavailable time slots, reservation cancellation, and reservation updates.

Only report tests as passed after actually running them.

## 4. Token Usage

- **AI tool:** ChatGPT by OpenAI
- **Plan used:** Free version
- **Purpose:** Code review, debugging, and programming assistance
- **Exact token count:** Not available
- **Token usage logs:** No verified token usage report was available for this documentation.

The free version of ChatGPT was used for the development assistance described above. An exact token count cannot be provided because verified token-usage statistics were not available.

## 5. Transparency and Verification

ChatGPT provided suggestions to support the development process. The developer is responsible for reviewing the suggested code, integrating the changes, and testing the final application.

The TableTalk reservation assistant uses programmed rules for handling reservation requests. Using ChatGPT during development does not mean that a ChatGPT API or external AI model is integrated into the running application.
