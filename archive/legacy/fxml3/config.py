"""Configuration settings for the FXML3 project."""

import os
import dotenv
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

import yaml

# Load environment variables from .env file
dotenv.load_dotenv()


@dataclass
class DataConfig:
    """Configuration for data acquisition and processing."""

    source: str = "yahoo"  # Options: "yahoo", "fxcm", "csv"
    symbols: List[str] = None  # Default symbols to analyze
    timeframes: List[str] = None  # Default timeframes to use
    start_date: str = "2020-01-01"  # Default start date
    end_date: str = None  # Default to current date if None
    cache_dir: str = "data/cache"  # Directory to cache downloaded data
    api_key: Optional[str] = None  # API key for data sources that require it
    
    def __post_init__(self):
        """Initialize default values."""
        if self.symbols is None:
            self.symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        if self.timeframes is None:
            self.timeframes = ["1H", "4H", "1D"]
            
        # Load API key from environment if available
        if self.api_key is None:
            env_key = os.environ.get("FOREX_API_KEY")
            if env_key:
                self.api_key = env_key


@dataclass
class WaveConfig:
    """Configuration for Elliott Wave analysis."""

    min_wave_size: float = 0.01  # Minimum size for a valid wave (%)
    max_wave_size: float = 10.0  # Maximum size for a valid wave (%)
    fib_tolerance: float = 0.1  # Tolerance for Fibonacci ratios
    peak_trough_threshold: float = 0.5  # Threshold for peak/trough detection
    wave_overlap_tolerance: float = 0.1  # Tolerance for wave overlap rules
    max_subwave_count: int = 5  # Maximum number of subwaves to analyze
    validation_methods: List[str] = None  # Methods to validate waves
    
    def __post_init__(self):
        """Initialize default values."""
        if self.validation_methods is None:
            self.validation_methods = ["fibonacci", "pattern", "time"]


@dataclass
class LLMConfig:
    """Configuration for LLM integration."""

    model_name: str = "gpt-3.5-turbo"  # Default LLM model
    api_key_env: str = "OPENAI_API_KEY"  # Environment variable for API key
    api_key: Optional[str] = None  # API key if not from environment
    use_local_model: bool = False  # Whether to use a local model
    local_model_path: Optional[str] = None  # Path to local model
    max_tokens: int = 1024  # Maximum tokens in responses
    temperature: float = 0.7  # Sampling temperature
    knowledge_base_dir: str = "data/knowledge"  # Directory for RAG documents
    
    def __post_init__(self):
        """Initialize values from environment if available."""
        # Get API key from environment if specified
        if self.api_key is None:
            env_key = os.environ.get(self.api_key_env)
            if env_key:
                self.api_key = env_key
                
        # Check for model override in environment
        env_model = os.environ.get("LLM_MODEL")
        if env_model:
            self.model_name = env_model
            
        # Check for local model path in environment
        if self.use_local_model and self.local_model_path is None:
            env_path = os.environ.get("LOCAL_MODEL_PATH")
            if env_path:
                self.local_model_path = env_path


@dataclass
class RLConfig:
    """Configuration for Reinforcement Learning."""

    algorithm: str = "PPO"  # RL algorithm to use
    learning_rate: float = 0.0003  # Learning rate
    gamma: float = 0.99  # Discount factor
    buffer_size: int = 10000  # Experience replay buffer size
    batch_size: int = 64  # Batch size for training
    training_epochs: int = 10  # Number of epochs per training update
    model_save_path: str = "models/rl"  # Path to save trained models


@dataclass
class UIConfig:
    """Configuration for user interface."""

    framework: str = "streamlit"  # UI framework to use
    theme: str = "light"  # UI theme
    default_chart_type: str = "candlestick"  # Default chart type
    port: int = 8501  # Port for web server
    debug: bool = False  # Debug mode


@dataclass
class Config:
    """Main configuration class that includes all sub-configurations."""

    data: DataConfig = None
    wave: WaveConfig = None
    llm: LLMConfig = None
    rl: RLConfig = None
    ui: UIConfig = None
    project_root: str = None
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Initialize default values."""
        if self.data is None:
            self.data = DataConfig()
        if self.wave is None:
            self.wave = WaveConfig()
        if self.llm is None:
            self.llm = LLMConfig()
        if self.rl is None:
            self.rl = RLConfig()
        if self.ui is None:
            self.ui = UIConfig()
        if self.project_root is None:
            self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        # Check for environment variables that override config
        env_log_level = os.environ.get("LOG_LEVEL")
        if env_log_level:
            self.log_level = env_log_level
            
        # Data source from environment
        env_data_source = os.environ.get("DATA_SOURCE")
        if env_data_source:
            self.data.source = env_data_source
            
        # Data cache directory from environment
        env_cache_dir = os.environ.get("DATA_CACHE_DIR")
        if env_cache_dir:
            self.data.cache_dir = env_cache_dir
            
        # RL model path from environment
        env_rl_path = os.environ.get("RL_MODEL_PATH")
        if env_rl_path:
            self.rl.model_save_path = env_rl_path
            
        # UI port from environment
        env_ui_port = os.environ.get("UI_PORT")
        if env_ui_port:
            try:
                self.ui.port = int(env_ui_port)
            except ValueError:
                pass  # Ignore if not a valid integer
                
        # UI debug mode from environment
        env_ui_debug = os.environ.get("UI_DEBUG")
        if env_ui_debug:
            self.ui.debug = env_ui_debug.lower() == "true"
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Config":
        """Load configuration from a YAML file.
        
        Args:
            yaml_path: Path to the YAML configuration file
            
        Returns:
            Config object with values from the YAML file
        """
        with open(yaml_path, "r") as f:
            config_dict = yaml.safe_load(f)
        
        # Create configurations from dict
        data_config = DataConfig(**config_dict.get("data", {}))
        wave_config = WaveConfig(**config_dict.get("wave", {}))
        llm_config = LLMConfig(**config_dict.get("llm", {}))
        rl_config = RLConfig(**config_dict.get("rl", {}))
        ui_config = UIConfig(**config_dict.get("ui", {}))
        
        return cls(
            data=data_config,
            wave=wave_config,
            llm=llm_config,
            rl=rl_config,
            ui=ui_config,
            project_root=config_dict.get("project_root"),
            log_level=config_dict.get("log_level", "INFO"),
        )
    
    def to_yaml(self, yaml_path: str) -> None:
        """Save configuration to a YAML file.
        
        Args:
            yaml_path: Path to save the YAML configuration file
        """
        config_dict = {
            "data": self.data.__dict__,
            "wave": self.wave.__dict__,
            "llm": self.llm.__dict__,
            "rl": self.rl.__dict__,
            "ui": self.ui.__dict__,
            "project_root": self.project_root,
            "log_level": self.log_level,
        }
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
        
        with open(yaml_path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False)


# Default configuration instance
CONFIG = Config()