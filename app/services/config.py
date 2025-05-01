
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel
import json
import os

class AgentTransferConfig(BaseModel):
    """Configuration for agent transfers."""
    enabled: bool = True
    default_threshold: float = 0.6
    min_messages_before_transfer: int = 2
    max_transfers_per_conversation: int = 5
    default_transfer_penalty: float = 0.1
    cool_down_messages: int = 3  # Min messages before considering another transfer
    topic_change_bonus: float = 0.2  # Bonus when topic changes significantly
    
class MemoryConfig(BaseModel):
    """Configuration for memory system."""
    enabled: bool = True
    vector_db_url: Optional[str] = None
    summary_frequency: int = 10  # Messages
    summary_time_threshold: int = 1800  # Seconds (30 mins)
    max_memories_per_query: int = 5
    memory_relevance_threshold: float = 0.6
    memory_decay_rate: float = 0.01  # Per day
    cleanup_age_days: int = 90
    
class RAGConfig(BaseModel):
    """Configuration for RAG system."""
    enabled: bool = True
    default_limit: int = 5
    min_relevance_score: float = 0.7
    categories_hard_limit: int = 3
    
class MCPConfig(BaseModel):
    """Configuration for MCP (function calling)."""
    enabled: bool = True
    max_function_calls_per_message: int = 3
    functions_require_approval: bool = True
    external_api_timeout: int = 10  # Seconds

class LoggingLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    
class LoggingConfig(BaseModel):
    """Configuration for logging."""
    level: LoggingLevel = LoggingLevel.INFO
    log_to_file: bool = True
    log_file_path: str = "./logs/agent_system.log"
    log_rotation: bool = True
    max_log_size_mb: int = 10
    
class SystemConfig(BaseModel):
    """Main configuration for the agent system."""
    agent_transfer: AgentTransferConfig = AgentTransferConfig()
    memory: MemoryConfig = MemoryConfig()
    rag: RAGConfig = RAGConfig()
    mcp: MCPConfig = MCPConfig()
    logging: LoggingConfig = LoggingConfig()
    
    # Additional system-wide settings
    default_tenant_id: Optional[str] = None
    default_agent_id: Optional[str] = None
    max_conversation_length: int = 100
    conversation_timeout_minutes: int = 60
    enable_escalation_to_human: bool = True
    
    # Override settings from environment variables or file
    def load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Agent Transfer
        if os.getenv("AGENT_TRANSFER_ENABLED"):
            self.agent_transfer.enabled = os.getenv("AGENT_TRANSFER_ENABLED").lower() == "true"
        if os.getenv("AGENT_TRANSFER_THRESHOLD"):
            self.agent_transfer.default_threshold = float(os.getenv("AGENT_TRANSFER_THRESHOLD"))
            
        # Memory
        if os.getenv("MEMORY_ENABLED"):
            self.memory.enabled = os.getenv("MEMORY_ENABLED").lower() == "true"
        if os.getenv("VECTOR_DB_URL"):
            self.memory.vector_db_url = os.getenv("VECTOR_DB_URL")
            
        # RAG
        if os.getenv("RAG_ENABLED"):
            self.rag.enabled = os.getenv("RAG_ENABLED").lower() == "true"
            
        # MCP
        if os.getenv("MCP_ENABLED"):
            self.mcp.enabled = os.getenv("MCP_ENABLED").lower() == "true"
        if os.getenv("MCP_REQUIRE_APPROVAL"):
            self.mcp.functions_require_approval = os.getenv("MCP_REQUIRE_APPROVAL").lower() == "true"
            
        # System
        if os.getenv("DEFAULT_TENANT_ID"):
            self.default_tenant_id = os.getenv("DEFAULT_TENANT_ID")
        if os.getenv("DEFAULT_AGENT_ID"):
            self.default_agent_id = os.getenv("DEFAULT_AGENT_ID")
        if os.getenv("ENABLE_HUMAN_ESCALATION"):
            self.enable_escalation_to_human = os.getenv("ENABLE_HUMAN_ESCALATION").lower() == "true"
    
    def load_from_file(self, file_path: str) -> None:
        """Load configuration from a JSON file."""
        try:
            with open(file_path, "r") as f:
                config_data = json.load(f)
                
            # Update main config
            for key, value in config_data.items():
                if key in self.__dict__ and isinstance(value, dict):
                    # Update nested config
                    nested_config = getattr(self, key)
                    for nested_key, nested_value in value.items():
                        if nested_key in nested_config.__dict__:
                            setattr(nested_config, nested_key, nested_value)
                elif key in self.__dict__:
                    setattr(self, key, value)
                    
        except Exception as e:
            print(f"Error loading config from file: {e}")
    
    def save_to_file(self, file_path: str) -> None:
        """Save current configuration to a JSON file."""
        try:
            config_dict = self.dict()
            with open(file_path, "w") as f:
                json.dump(config_dict, f, indent=2)
        except Exception as e:
            print(f"Error saving config to file: {e}")
    
    def get_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant-specific configuration overrides."""
        # This would normally be loaded from a database
        # For now, we'll return empty dict (no overrides)
        return {}
        
    def apply_tenant_overrides(self, tenant_id: str) -> 'SystemConfig':
        """Create a new config with tenant-specific overrides applied."""
        tenant_config = self.get_tenant_config(tenant_id)
        if not tenant_config:
            return self
            
        # Create a copy of this config
        new_config = SystemConfig.parse_obj(self.dict())
        
        # Apply tenant overrides
        for key, value in tenant_config.items():
            if key in new_config.__dict__ and isinstance(value, dict):
                # Update nested config
                nested_config = getattr(new_config, key)
                for nested_key, nested_value in value.items():
                    if nested_key in nested_config.__dict__:
                        setattr(nested_config, nested_key, nested_value)
            elif key in new_config.__dict__:
                setattr(new_config, key, value)
                
        return new_config
    
def load_system_config() -> SystemConfig:
    """
    Carrega a configuração do sistema a partir de variáveis de ambiente e arquivo de configuração.
    
    Returns:
        Uma instância configurada de SystemConfig
    """
    config = SystemConfig()
    
    # Carregar variáveis de ambiente
    config.load_from_env()
    
    # Carregar do arquivo de configuração, se existir
    config_file = os.getenv("AGENT_SYSTEM_CONFIG", "./config/agent_system.json")
    if os.path.exists(config_file):
        config.load_from_file(config_file)
    
    # Configurar caminhos de logs
    if config.logging.log_to_file:
        log_dir = os.path.dirname(config.logging.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    return config