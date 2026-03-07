import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")


async def generate_email(team_context: dict, organization: str, email_type: str, subject_line: str) -> str:
    prompt = f"""
Write a professional {email_type} email from {team_context['team_name']} to {organization}.

Subject: {subject_line}

Team context:
- Subsystems: {', '.join(team_context['subsystems'])}
- Tech stack: {', '.join(team_context['tech_stack'])}
- Current blockers: {', '.join(team_context['blockers'])}

Requirements:
- Tone: professional, concise, direct
- Length: 150-250 words
- Start with "Subject: ..." on the first line
- No placeholders — write a complete, sendable draft
- {"Request sponsorship or resources" if email_type == "sponsorship" else "Propose collaboration or outreach"}
"""
    response = await model.generate_content_async(prompt)
    return response.text
