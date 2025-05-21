import os
import json
import abc
from typing import List, Dict, Optional, Any, Union

class LyricsGenerator(abc.ABC):
    """Base abstract class for lyrics generation"""
    
    @abc.abstractmethod
    def generate_lyrics(self, prompt: str) -> str:
        """Generate lyrics based on a prompt"""
        pass
    
    @abc.abstractmethod
    def extract_genre(self, prompt: str) -> str:
        """Extract a genre from a prompt"""
        pass
    
    @abc.abstractmethod
    def infer_genres(self, prompt: str) -> List[str]:
        """Infer multiple genres from a prompt"""
        pass
    
    @abc.abstractmethod
    def generate_lyrics_with_genres(self, prompt: str, genres: List[str]) -> str:
        """Generate lyrics that incorporate elements from specified genres"""
        pass
    
    def read_lyrics_prompt(self, file_path: str, default_prompt: str = "") -> str:
        """Read lyrics prompt from file or return default
        
        Args:
            file_path: Path to the lyrics prompt file
            default_prompt: Default prompt to use if file doesn't exist or is empty
            
        Returns:
            The prompt text to use
        """
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    saved_prompt = f.read()
                    if saved_prompt.strip():
                        return saved_prompt
        except Exception as e:
            print(f"Error reading lyrics prompt file: {str(e)}")
        
        return default_prompt
    
    def read_genre_prompt(self, file_path: str, default_prompt: str = "") -> str:
        """Read genre prompt from file or return default
        
        Args:
            file_path: Path to the genre prompt file
            default_prompt: Default prompt to use if file doesn't exist or is empty
            
        Returns:
            The prompt text to use
        """
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    saved_prompt = f.read()
                    return saved_prompt
        except Exception as e:
            print(f"Error reading genre prompt file: {str(e)}")
        
        return default_prompt
    
    def write_lyrics_prompt(self, file_path: str, prompt: str) -> bool:
        """Write lyrics prompt to file
        
        Args:
            file_path: Path to the lyrics prompt file
            prompt: Prompt text to write
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, 'w') as f:
                f.write(prompt)
            print(f"Saved lyrics prompt to {file_path}")
            return True
        except Exception as e:
            print(f"Error saving lyrics prompt: {str(e)}")
            return False
    
    def write_genre_prompt(self, file_path: str, prompt: str) -> bool:
        """Write genre prompt to file
        
        Args:
            file_path: Path to the genre prompt file
            prompt: Prompt text to write
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, 'w') as f:
                f.write(prompt)
            print(f"Saved genre prompt to {file_path}")
            return True
        except Exception as e:
            print(f"Error saving genre prompt: {str(e)}")
            return False


class OpenAILyricsGenerator(LyricsGenerator):
    """Lyrics generator using OpenAI API"""
    
    # Default models to try in order
    FALLBACK_MODELS = [
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo"
    ]
    
    def __init__(self, api_key: str, model_name: str = None):
        """Initialize the OpenAI lyrics generator
        
        Args:
            api_key: OpenAI API key
            model_name: OpenAI model name to use
        """
        import openai
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)
        
        # Try to find a working model
        self.model_name = model_name if model_name else self.FALLBACK_MODELS[0]
        self._validate_model()
    
    def _validate_model(self):
        """Try to find a working model by testing fallbacks"""
        if not self.model_name:
            self.model_name = self.FALLBACK_MODELS[0]
            
        # If model_name isn't in our fallbacks, add it at the start
        models_to_try = []
        if self.model_name not in self.FALLBACK_MODELS:
            models_to_try.append(self.model_name)
        models_to_try.extend(self.FALLBACK_MODELS)
            
        working_model = None
        errors = []
        
        # Try each model in sequence
        for model in models_to_try:
            try:
                # Simple test message to check if model exists
                message = self.client.chat.completions.create(
                    model=model,
                    max_tokens=10,
                    messages=[
                        {"role": "system", "content": "Reply with 'OK'"},
                        {"role": "user", "content": "test"}
                    ]
                )
                working_model = model
                print(f"Successfully validated model: {model}")
                break
            except Exception as e:
                errors.append(f"{model}: {str(e)}")
                print(f"Model {model} failed validation: {str(e)}")
                continue
        
        if working_model:
            self.model_name = working_model
        else:
            error_detail = "\n".join(errors)
            raise ValueError(f"Could not find a working OpenAI model. Errors:\n{error_detail}")
    
    def generate_lyrics(self, prompt: str, lyrics_prompt: str = None) -> str:
        """Generate lyrics using OpenAI API
        
        Args:
            prompt: User's prompt about the song
            lyrics_prompt: System prompt for lyrics generation
        
        Returns:
            Generated lyrics as a string
        """
        if not lyrics_prompt:
            # Use a default prompt if not provided
            lyrics_prompt = self._get_default_lyrics_prompt()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": lyrics_prompt},
                    {"role": "user", "content": f"Prompt: {prompt}"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error in OpenAI lyrics generation: {str(e)}")
            raise
    
    def extract_genre(self, prompt: str, genre_prompt: str = None) -> str:
        """Extract a genre from the prompt using OpenAI
        
        Args:
            prompt: User's prompt about the song
            genre_prompt: Custom system prompt for genre extraction
        
        Returns:
            Extracted genre as a string
        """
        base_prompt = """Based on the given prompt, determine the most suitable musical genre for the song.
        Respond with just a single word genre (e.g., 'rock', 'pop', 'jazz', 'hiphop', 'blues', etc.).
        Do not include any explanations or additional text."""
        
        combined_prompt = base_prompt
        if genre_prompt and genre_prompt.strip():
            combined_prompt = f"{base_prompt}\n\n{genre_prompt}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                max_tokens=50,
                messages=[
                    {"role": "system", "content": combined_prompt},
                    {"role": "user", "content": f"Prompt: {prompt}"}
                ]
            )
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            print(f"Error in OpenAI genre extraction: {str(e)}")
            raise
    
    def infer_genres(self, prompt: str) -> List[str]:
        """Infer multiple suitable genres from the prompt using OpenAI
        
        Args:
            prompt: User's prompt about the song
        
        Returns:
            List of inferred genres
        """
        system_prompt = """As a music expert, analyze the given prompt and suggest 2-3 most suitable musical genres that would work well together.
        Consider:
        1. The theme and mood of the prompt
        2. Common genre combinations in modern music
        3. Musical compatibility between genres
        
        Respond with ONLY a comma-separated list of genres (e.g., 'rock, electronic, indie').
        Do not include any explanations or additional text."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                max_tokens=100,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Prompt: {prompt}"}
                ]
            )
            return [g.strip().lower() for g in response.choices[0].message.content.split(',')]
        except Exception as e:
            print(f"Error in OpenAI genre inference: {str(e)}")
            raise
    
    def generate_lyrics_with_genres(self, prompt: str, genres: List[str]) -> str:
        """Generate lyrics that incorporate elements from specified genres
        
        Args:
            prompt: User's prompt about the song
            genres: List of genres to incorporate in the lyrics
        
        Returns:
            Generated lyrics as a string
        """
        system_prompt = f"""You are a professional songwriter. Generate song lyrics based on the given prompt that incorporate elements from the following genres: {', '.join(genres)}.
        The lyrics MUST follow this exact structure and format:
        - [verse]
        - [chorus]
        - [verse]
        - [chorus]
        - [bridge]
        - [outro]

        Each section should be separated by exactly two newlines (\n\n).
        Within each section, lines should be separated by a single newline (\n).
        Each section should be marked with its type in square brackets (e.g., [verse], [chorus], etc.).
        
        The lyrics should:
        1. Include typical elements, themes, and style from the specified genres
        2. Use appropriate vocabulary and metaphors common in these genres
        3. Follow common rhyme patterns for these genres
        4. Maintain appropriate tone and mood for these genres
        
        Do not include any explanations or additional text - just the lyrics in the specified format."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Prompt: {prompt}"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error in OpenAI genre-specific lyrics generation: {str(e)}")
            raise
    
    def _get_default_lyrics_prompt(self) -> str:
        """Returns the default system prompt for lyrics generation"""
        return """You are a professional songwriter. Generate song lyrics based on the given prompt.
        The lyrics MUST follow this exact structure and format:
        - [verse]
        - [chorus]
        - [verse]
        - [chorus]
        - [bridge]
        - [outro]

        Each section should be separated by exactly two newlines (\n\n).
        Within each section, lines should be separated by a single newline (\n).
        Each section should be marked with its type in square brackets (e.g., [verse], [chorus], etc.).

        Example format:
        [verse]
        Line 1
        Line 2
        Line 3
        Line 4

        [chorus]
        Line 1
        Line 2
        Line 3
        Line 4

        [verse]
        ...and so on.

        The lyrics should be creative, meaningful, and suitable for singing. Do not include any explanations or additional text - just the lyrics in the specified format."""


def create_lyrics_generator(provider: str = 'openai', api_key: str = None, model_name: Optional[str] = None) -> LyricsGenerator:
    """Factory function to create the appropriate lyrics generator
    
    Args:
        provider: Provider name (only 'openai' supported), defaults to 'openai'
        api_key: API key for the selected provider
        model_name: Optional model name (uses default if not specified)
    
    Returns:
        An instance of LyricsGenerator
    """
    provider = provider.lower()
    
    if provider == 'openai':
        # For OpenAI, we let the class handle model selection with fallbacks
        return OpenAILyricsGenerator(api_key, model_name)
    else:
        raise ValueError(f"Unsupported provider: {provider}. Supported: 'openai'") 