import re
import fitz  # PyMuPDF
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ParsedPaper:
    """Container for parsed paper data."""
    title: Optional[str] = None
    authors: Optional[list] = None
    abstract: Optional[str] = None
    full_text: str = ""
    doi: Optional[str] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    sections: Optional[Dict[str, str]] = None


class PDFParser:
    """PDF parsing service for academic papers."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = None

    def __enter__(self):
        self.doc = fitz.open(self.pdf_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.doc:
            self.doc.close()

    def extract_full_text(self) -> str:
        """Extract all text from the PDF."""
        text_parts = []
        for page in self.doc:
            text_parts.append(page.get_text())
        return "\n".join(text_parts)

    def extract_metadata(self) -> Dict[str, Any]:
        """Extract PDF metadata."""
        metadata = self.doc.metadata
        return {
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "subject": metadata.get("subject"),
            "keywords": metadata.get("keywords"),
            "creator": metadata.get("creator"),
            "producer": metadata.get("producer"),
        }

    def extract_title(self, text: str) -> Optional[str]:
        """Extract paper title from text (usually first large text on first page)."""
        # Try from metadata first
        if self.doc.metadata.get("title"):
            title = self.doc.metadata["title"].strip()
            if len(title) > 10:  # Reasonable title length
                return title

        # Try to extract from first page
        first_page = self.doc[0]
        blocks = first_page.get_text("dict")["blocks"]

        # Find the largest text block in the upper portion (likely title)
        candidates = []
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        if span["size"] > 12:  # Larger than body text
                            candidates.append({
                                "text": span["text"].strip(),
                                "size": span["size"],
                                "y": span["bbox"][1]
                            })

        # Sort by size (largest first) and position (top first)
        candidates.sort(key=lambda x: (-x["size"], x["y"]))

        if candidates:
            # Combine top candidates that might be multi-line title
            title_parts = []
            for c in candidates[:3]:
                if c["text"] and len(c["text"]) > 3:
                    title_parts.append(c["text"])
            if title_parts:
                return " ".join(title_parts[:2])  # Max 2 lines for title

        # Fallback: first substantial line
        lines = text.split("\n")
        for line in lines[:20]:
            line = line.strip()
            if len(line) > 20 and len(line) < 200:
                return line

        return None

    def extract_abstract(self, text: str) -> Optional[str]:
        """Extract abstract from paper text."""
        # Common patterns for abstract section
        patterns = [
            r"(?i)abstract[:\s]*\n?(.*?)(?=\n\s*(?:introduction|keywords|1\.|1\s|index terms))",
            r"(?i)abstract[:\s]*\n?(.*?)(?=\n\n)",
            r"(?i)summary[:\s]*\n?(.*?)(?=\n\s*(?:introduction|keywords|1\.))",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                abstract = match.group(1).strip()
                # Clean up the abstract
                abstract = re.sub(r'\s+', ' ', abstract)
                if len(abstract) > 100:  # Reasonable abstract length
                    return abstract[:2000]  # Limit length

        return None

    def extract_authors(self, text: str) -> Optional[list]:
        """Extract author names from paper."""
        # Try from metadata
        if self.doc.metadata.get("author"):
            authors_str = self.doc.metadata["author"]
            # Split by common delimiters
            authors = re.split(r'[,;]|\band\b', authors_str)
            authors = [a.strip() for a in authors if a.strip()]
            if authors:
                return authors

        # Try to extract from text (look after title, before abstract)
        lines = text.split("\n")[:30]

        # Look for email patterns to identify author section
        author_section = []
        for i, line in enumerate(lines):
            line = line.strip()
            # Skip empty lines and very long lines
            if not line or len(line) > 200:
                continue
            # Check for author-like patterns (names with possible affiliations)
            if re.search(r'@|university|department|institute', line, re.I):
                # Look at surrounding lines for names
                for j in range(max(0, i-5), i):
                    potential_name = lines[j].strip()
                    if potential_name and len(potential_name) < 100:
                        if re.match(r'^[A-Z][a-z]+\s+[A-Z]', potential_name):
                            author_section.append(potential_name)
                break

        if author_section:
            # Extract just the names
            authors = []
            for line in author_section:
                # Extract name pattern
                names = re.findall(r'[A-Z][a-z]+\s+(?:[A-Z]\.\s*)?[A-Z][a-z]+', line)
                authors.extend(names)
            return authors[:10] if authors else None

        return None

    def extract_doi(self, text: str) -> Optional[str]:
        """Extract DOI from paper."""
        # DOI pattern
        doi_pattern = r'10\.\d{4,}/[^\s]+'
        match = re.search(doi_pattern, text[:5000])  # Check first part of paper
        if match:
            doi = match.group()
            # Clean up DOI
            doi = re.sub(r'[.,;)\]]+$', '', doi)
            return doi
        return None

    def extract_year(self, text: str) -> Optional[int]:
        """Extract publication year from paper."""
        # Look for year patterns in common locations
        patterns = [
            r'(?:published|received|accepted|copyright)[:\s]*(?:\w+\s+)?(\d{4})',
            r'\b(19\d{2}|20[0-2]\d)\b',  # Year range 1900-2029
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text[:3000], re.I)
            if matches:
                # Return the most recent valid year
                years = [int(y) for y in matches if 1990 <= int(y) <= 2030]
                if years:
                    return max(years)

        return None

    def parse(self) -> ParsedPaper:
        """Parse the PDF and extract all information."""
        full_text = self.extract_full_text()

        return ParsedPaper(
            title=self.extract_title(full_text),
            authors=self.extract_authors(full_text),
            abstract=self.extract_abstract(full_text),
            full_text=full_text,
            doi=self.extract_doi(full_text),
            year=self.extract_year(full_text),
        )


def parse_pdf(pdf_path: str) -> ParsedPaper:
    """Convenience function to parse a PDF file."""
    with PDFParser(pdf_path) as parser:
        return parser.parse()
