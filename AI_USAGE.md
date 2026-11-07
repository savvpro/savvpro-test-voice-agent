# AI Usage Log

## Summary

This project is a voice-based appointment assistant for a clinic. It uses Python rules and a state machine to understand user requests, manage conversations, and handle appointment booking tasks.

Claude was used during development to assist with coding, problem-solving, reviewing implementation ideas, and preparing documentation. The running application does not depend on a large language model to make decisions. Its behavior is controlled by the Python code implemented in the project.

## Tools Used

- Claude (claude.ai) for development assistance.
- Python and `pytest` for running and checking backend tests.
- Git and GitHub for version control and project submission.

## How AI Assistance Was Used

Claude assisted with different stages of development, including:

- Planning the project structure and organizing files.
- Drafting and refining natural language understanding (NLU) rules.
- Working on the conversation flow and state machine.
- Developing FastAPI endpoints and backend functionality.
- Building React frontend components and the user interface.
- Preparing tests and project documentation.

Claude's suggestions were reviewed during development and adjusted where necessary to fit the application's requirements.

## AI Assistance in Logic Design and Decision-Making

Claude was used as a development aid to explore approaches for handling user requests and managing appointment conversations.

This included assistance with intent recognition, extracting appointment details, handling conversation states, validating user input, and organizing booking workflows.

The final behavior is implemented in the application's Python code. The application uses predefined rules, validation checks, and state transitions rather than asking an external AI model to decide what to do during a conversation.

## Where AI Assistance Was Most Useful

Claude was particularly useful for:

- Structuring the initial implementation.
- Developing and refining NLU rules for supported user requests.
- Organizing the conversation flow for appointment-related tasks.
- Identifying scenarios that should be tested.
- Improving the clarity and structure of the project documentation.

## Where AI Was Not Used at Runtime

The application does not use an external large language model as its runtime decision engine.

When a user interacts with the assistant, the application processes the input using its implemented logic. Depending on the request, it identifies an intent, validates the required details, checks appointment information, updates the conversation state, and generates a response using predefined rules and templates.

The browser handles speech-to-text and text-to-speech, while the backend manages the conversation logic and appointment operations.

This approach keeps the decision-making process predictable and makes the core behavior easier to test.

## Testing and Verification

The backend was tested using `pytest` to check the implemented functionality and identify issues during development.

Testing was used to verify the application's behavior against the scenarios covered by the test suite. Specific bugs and corrections should be documented here based on the actual development experience.

## Token and Usage Note

Claude was used for development assistance. Exact token usage has not been recorded in this document, so no token counts or usage estimates have been included.

Development-time AI assistance is separate from runtime application behavior. The application does not require an external LLM API to make appointment-booking decisions.


Some suggestions needed to be checked and adjusted during development. I used tests to check the application and identify issues. I prefer to include specific examples here only when I can confirm what happened and how I fixed it.

## Token Usage

I did not keep a record of the exact token usage, so I have not added any estimated numbers. I will include usage screenshots if they are available.


