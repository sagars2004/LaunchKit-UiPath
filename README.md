[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Hackathon: UiPath AgentHack](https://img.shields.io/badge/Hackathon-UiPath_AgentHack-blue.svg)](https://www.uipath.com/)

# LaunchKit
> AI-powered hackathon success pipeline

## Problem
The hackathon process can be overwhelming, with participants struggling to extract relevant information from unstructured event pages, research past winners, and generate high-quality submissions. This can lead to wasted time, effort, and a lower chance of winning. The current process lacks automation, making it difficult for participants to focus on the creative aspects of their projects.

## Solution
LaunchKit is a full-lifecycle hackathon success pipeline that addresses these challenges by providing a modular and automated solution. It utilizes natural language processing techniques, machine learning algorithms, and UiPath Maestro BPMN for pipeline orchestration to streamline the submission process. With LaunchKit, participants can focus on developing innovative projects, increasing their chances of winning.

## Demo
[Demo video coming soon]
![Screenshot coming soon](screenshot.png)

## Features
| Feature | Description |
| --- | --- |
| Hackathon Intelligence Agent | Scrapes hackathon event pages and extracts judging criteria using Devpost API and Gemini LLM |
| Winner Researcher Agent | Researches past Devpost winners and extracts submission patterns using Devpost API and Gemini LLM |
| Automated Submission Generation | Generates complete, published, analytics-tracked submissions using UiPath Maestro BPMN and Google Generative AI |

## Tech Stack
* Backend: FastAPI, Uvicorn
* Frontend: None
* Infrastructure: Supabase
* AI/ML: Google Generative AI, Gemini LLM

## Architecture
```mermaid
graph LR
    A[Hackathon Event Page] -->|Scrape|> B[Hackathon Intelligence Agent]
    B -->|Extract Judging Criteria|> C[Database]
    D[Past Devpost Winners] -->|Scrape|> E[Winner Researcher Agent]
    E -->|Extract Submission Patterns|> C
    F[User Input] -->|Generate Submission|> G[Automated Submission Generation]
    G -->|Publish and Track|> H[Submission]
    style B fill:#f9f,stroke:#333,stroke-width:4px
    style E fill:#f9f,stroke:#333,stroke-width:4px
    style G fill:#f9f,stroke:#333,stroke-width:4px
```

## Getting Started
1. Clone the repository: `git clone https://github.com/username/launchkit.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables: `cp .env.example .env` and update the values
4. Run the application: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

## Environment Variables
| Variable | Description | Required |
| --- | --- | --- |
| `DEVPOST_API_KEY` | Devpost API key | Yes |
| `GEMINI_LLM_API_KEY` | Gemini LLM API key | Yes |
| `SUPABASE_URL` | Supabase URL | Yes |
| `SUPABASE_KEY` | Supabase key | Yes |
| `UIPATH_MAESTRO_BPMN_URL` | UiPath Maestro BPMN URL | Yes |
| `GOOGLE_GENERATIVE_AI_API_KEY` | Google Generative AI API key | Yes |

## License
MIT License

Copyright (c) 2023 LaunchKit

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.