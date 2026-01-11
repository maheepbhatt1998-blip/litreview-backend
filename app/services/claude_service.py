import json
import re
from typing import Optional, Dict, Any, List
from anthropic import Anthropic
from app.config import settings


class ClaudeService:
    """Service for interacting with Claude API for paper analysis."""

    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL

    def _truncate_text(self, text: str, max_chars: int = 150000) -> str:
        """Truncate text to fit within token limits."""
        if len(text) > max_chars:
            return text[:max_chars] + "\n\n[Text truncated due to length...]"
        return text

    async def analyze_paper(
        self,
        title: Optional[str],
        abstract: Optional[str],
        full_text: str,
    ) -> Dict[str, Any]:
        """Analyze a research paper and extract key insights."""

        paper_content = self._truncate_text(full_text)

        prompt = f"""You are an expert research analyst. Analyze the following research paper and provide a comprehensive analysis.

Paper Title: {title or 'Unknown'}

Abstract: {abstract or 'Not available'}

Full Text:
{paper_content}

Please provide your analysis in the following JSON format (ensure valid JSON):
{{
    "importance": "A detailed explanation of why this paper is significant, what problem it addresses, and its potential impact on the field. Be specific about the contributions.",
    "importance_score": <integer from 1-10>,
    "novelty": "Explain what is new in this paper compared to conventional/previous approaches. Describe the key innovations and how they differ from prior work.",
    "conventional_methods": ["List of previous/conventional methods mentioned or compared against"],
    "innovations": ["List of specific innovations or new contributions introduced by this paper"],
    "methodology": "A clear, accessible explanation of the methodology and approach used. Explain it in a way that someone with general technical knowledge can understand.",
    "results_summary": "Detailed summary of the key results with specific numbers, metrics, and comparisons where available. Explain what these results mean in practical terms.",
    "key_findings": {{
        "main_result": "The primary finding or achievement",
        "metrics": {{"metric_name": "value"}},
        "comparisons": ["How results compare to baselines or previous work"]
    }},
    "future_work": "Identify potential future research directions, limitations of the current work, and open questions that remain. Suggest specific areas for improvement.",
    "key_takeaways": ["5-7 bullet points summarizing the most important aspects of this paper"]
}}

IMPORTANT:
- Respond ONLY with valid JSON, no additional text
- Be thorough and specific in your analysis
- Include actual numbers and metrics where available
- Focus on practical implications and real-world applications"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text

            # Try to parse JSON response
            try:
                # Clean up response if needed
                response_text = response_text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]

                analysis = json.loads(response_text)
                return analysis

            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract sections manually
                return self._parse_unstructured_response(response_text)

        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")

    def _parse_unstructured_response(self, text: str) -> Dict[str, Any]:
        """Fallback parser for non-JSON responses."""
        sections = {
            "importance": "",
            "importance_score": 5,
            "novelty": "",
            "methodology": "",
            "results_summary": "",
            "future_work": "",
            "key_takeaways": [],
            "conventional_methods": [],
            "innovations": [],
            "key_findings": {},
        }

        # Try to extract sections based on keywords
        current_section = None
        lines = text.split("\n")

        for line in lines:
            line_lower = line.lower().strip()

            if "importance" in line_lower and ":" in line:
                current_section = "importance"
            elif "novelty" in line_lower or "new" in line_lower and ":" in line:
                current_section = "novelty"
            elif "methodology" in line_lower or "method" in line_lower and ":" in line:
                current_section = "methodology"
            elif "result" in line_lower and ":" in line:
                current_section = "results_summary"
            elif "future" in line_lower and ":" in line:
                current_section = "future_work"
            elif "takeaway" in line_lower or "summary" in line_lower and ":" in line:
                current_section = "key_takeaways"
            elif current_section and current_section != "key_takeaways":
                sections[current_section] += line + "\n"
            elif current_section == "key_takeaways" and line.strip().startswith("-"):
                sections["key_takeaways"].append(line.strip()[1:].strip())

        return sections

    async def generate_project_insights(
        self,
        project_topic: Optional[str],
        paper_summaries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate cross-paper insights for a project."""

        papers_text = ""
        for i, paper in enumerate(paper_summaries, 1):
            papers_text += f"""
Paper {i}: {paper.get('title', 'Unknown')}
Year: {paper.get('year', 'Unknown')}
Key Contributions: {paper.get('importance', 'Not analyzed')}
Methodology: {paper.get('methodology', 'Not analyzed')}
Results: {paper.get('results_summary', 'Not analyzed')}
---
"""

        prompt = f"""You are an expert research analyst conducting a literature review. Analyze the following collection of {len(paper_summaries)} research papers and identify patterns, gaps, and opportunities.

Research Topic: {project_topic or 'Not specified'}

Papers in the Collection:
{papers_text}

Please provide your analysis in the following JSON format:
{{
    "research_trends": {{
        "title": "Research Trends and Patterns",
        "content": "Detailed analysis of trends across the papers, common themes, evolving methodologies, and how the field has progressed."
    }},
    "research_gaps": {{
        "title": "Research Gaps and Opportunities",
        "content": "Identify what's missing in the current research, unexplored areas, and potential opportunities for new research."
    }},
    "methodology_comparison": {{
        "title": "Methodology Comparison",
        "content": "Compare and contrast the methodologies used across papers. Identify strengths and weaknesses of different approaches."
    }},
    "novel_ideas": {{
        "title": "Suggested Research Directions",
        "content": "Based on the analysis, suggest 3-5 novel research ideas that combine insights from multiple papers or address identified gaps."
    }},
    "synthesis": {{
        "title": "Literature Synthesis",
        "content": "A cohesive narrative that synthesizes the key findings across all papers and their implications for the field."
    }}
}}

IMPORTANT: Respond ONLY with valid JSON. Be specific and reference actual papers where relevant."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text

            # Clean up and parse JSON
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            return json.loads(response_text)

        except Exception as e:
            raise Exception(f"Claude API error generating insights: {str(e)}")


# Singleton instance
claude_service = ClaudeService()
