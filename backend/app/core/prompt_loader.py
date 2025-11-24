"""Prompt template loader for model-specific configurations"""

import yaml
import os
from typing import Dict, Any, List, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Required prompts that must be defined in every template
REQUIRED_PROMPTS = [
    'intelligence_analysis',
    'daily_summary',
    'research_basic_info',
    'research_executives',
    'research_competitors',
    'research_keywords',
    'research_sources'
]


class ModelConfig:
    """Configuration for a single model"""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.model_name = config['name']
        self.provider = config['provider']
        self.api_base = config['api_base']
        self.api_key_env = config.get('api_key_env', '')
        self.tier = config.get('tier', 'frontier')
        self.max_tokens = config.get('max_tokens', 800)

        # Get API key from environment if specified
        self.api_key = os.getenv(self.api_key_env, '') if self.api_key_env else ''

    def __repr__(self):
        return f"ModelConfig({self.model_name}, provider={self.provider}, tier={self.tier})"


class PromptConfig:
    """Configuration for a single prompt"""

    def __init__(self, name: str, model_config: ModelConfig, template: str):
        self.name = name
        self.model = model_config
        self.template = template

    def format(self, **kwargs) -> str:
        """Format the template with variables"""
        return self.template.format(**kwargs)

    def __repr__(self):
        return f"PromptConfig({self.name}, model={self.model.model_name})"


class PromptTemplate:
    """Model-specific prompt template configuration with per-prompt model assignment"""

    def __init__(self, config_path: str):
        """Load prompt template from YAML file"""
        self.config_path = config_path
        self.config = self._load_config()

        # Load model definitions
        self.models: Dict[str, ModelConfig] = {}
        for model_name, model_config in self.config['models'].items():
            self.models[model_name] = ModelConfig(model_name, model_config)

        # Load prompts with their model assignments
        self.prompts: Dict[str, PromptConfig] = {}
        for prompt_name, prompt_data in self.config['prompts'].items():
            model_ref = prompt_data['model']

            # Validate model reference
            if model_ref not in self.models:
                raise ValueError(
                    f"Prompt '{prompt_name}' references unknown model '{model_ref}'. "
                    f"Available models: {list(self.models.keys())}"
                )

            model_config = self.models[model_ref]
            template = prompt_data['template']

            self.prompts[prompt_name] = PromptConfig(prompt_name, model_config, template)

        # Validate all required prompts are present
        self._validate_required_prompts()

        logger.info(
            f"Loaded prompt template: {config_path} "
            f"({len(self.prompts)} prompts, {len(self.models)} models)"
        )

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML configuration file"""
        # Support both absolute paths and relative paths from config/prompts/
        if os.path.isabs(self.config_path):
            config_file = Path(self.config_path)
        else:
            # Go up 3 levels from app/core/prompt_loader.py to reach /app (Docker) or project root
            # Docker: /app/app/core/prompt_loader.py -> /app/config/prompts/
            # Local: /path/to/hermes/backend/app/core/prompt_loader.py -> /path/to/hermes/config/prompts/
            config_file = Path(__file__).parent.parent.parent / 'config' / 'prompts' / self.config_path

        if not config_file.exists():
            raise FileNotFoundError(f"Prompt template not found: {config_file}")

        with open(config_file, 'r') as f:
            return yaml.safe_load(f)

    def _validate_required_prompts(self):
        """Validate that all required prompts are defined"""
        missing_prompts = []
        for required_prompt in REQUIRED_PROMPTS:
            if required_prompt not in self.prompts:
                missing_prompts.append(required_prompt)

        if missing_prompts:
            raise ValueError(
                f"Template '{self.config_path}' is missing required prompts: {missing_prompts}. "
                f"All templates must define: {REQUIRED_PROMPTS}"
            )

    def get_prompt(self, prompt_name: str) -> PromptConfig:
        """
        Get a prompt configuration including its model and template

        Returns:
            PromptConfig with model configuration and template
        """
        if prompt_name not in self.prompts:
            raise ValueError(
                f"Prompt '{prompt_name}' not found in template {self.config_path}. "
                f"Available prompts: {list(self.prompts.keys())}"
            )

        return self.prompts[prompt_name]

    def format_prompt(self, prompt_name: str, **kwargs) -> Tuple[str, ModelConfig]:
        """
        Get and format a prompt with variables, along with its model configuration

        Returns:
            Tuple of (formatted_prompt, model_config)
        """
        prompt_config = self.get_prompt(prompt_name)
        formatted_template = prompt_config.format(**kwargs)
        return formatted_template, prompt_config.model

    def get_model(self, model_name: str) -> ModelConfig:
        """Get a model configuration by name"""
        if model_name not in self.models:
            raise ValueError(
                f"Model '{model_name}' not found in template {self.config_path}. "
                f"Available models: {list(self.models.keys())}"
            )

        return self.models[model_name]

    def list_prompts(self) -> List[str]:
        """Get list of all available prompt names"""
        return list(self.prompts.keys())

    def list_models(self) -> List[str]:
        """Get list of all available model names"""
        return list(self.models.keys())

    def __repr__(self):
        return (
            f"PromptTemplate({self.config_path}, "
            f"prompts={list(self.prompts.keys())}, "
            f"models={list(self.models.keys())})"
        )


def load_prompt_template(template_name: str) -> PromptTemplate:
    """
    Load a prompt template by name

    Args:
        template_name: Name of the template file (with or without .yaml extension)

    Returns:
        PromptTemplate instance

    Example:
        template = load_prompt_template('qwen3-4b')

        # Get prompt with its model config
        prompt_config = template.get_prompt('intelligence_analysis')
        print(f"Using model: {prompt_config.model.model_name}")

        # Format and get model in one call
        formatted_prompt, model = template.format_prompt(
            'intelligence_analysis',
            customer_name='NBN Co',
            title='...',
            content='...'
        )
    """
    if not template_name.endswith('.yaml'):
        template_name = f"{template_name}.yaml"

    return PromptTemplate(template_name)


def get_available_templates() -> List[str]:
    """Get list of available prompt templates"""
    prompts_dir = Path(__file__).parent.parent.parent / 'config' / 'prompts'

    if not prompts_dir.exists():
        return []

    return [f.stem for f in prompts_dir.glob('*.yaml')]
