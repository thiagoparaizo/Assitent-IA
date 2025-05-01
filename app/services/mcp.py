# app/services/mcp.py
from typing import Dict, List, Any, Optional, Callable
import inspect
import asyncio
import json

class MCPFunction:
    """Representa uma função que pode ser chamada pelo MCP."""
    
    def __init__(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        self.description = description or func.__doc__ or ""
        self.signature = self._get_signature()
    
    def _get_signature(self) -> Dict[str, Any]:
        """Extrai a assinatura da função como um esquema JSON."""
        sig = inspect.signature(self.func)
        params = {}
        
        for name, param in sig.parameters.items():
            if param.annotation == inspect.Parameter.empty:
                param_type = "string"
            elif param.annotation == str:
                param_type = "string"
            elif param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == List:
                param_type = "array"
            elif param.annotation == Dict:
                param_type = "object"
            else:
                param_type = "string"
            
            params[name] = {
                "type": param_type,
                "description": "",
                "required": param.default == inspect.Parameter.empty
            }
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": params
        }
    
    async def execute(self, **kwargs) -> Any:
        """Executa a função com os parâmetros fornecidos."""
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        else:
            return self.func(**kwargs)

class MCPService:
    """Serviço para gerenciamento de funções MCP."""
    
    def __init__(self):
        self.functions: Dict[str, MCPFunction] = {}
    
    def register_function(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> MCPFunction:
        """Registra uma função para uso com MCP."""
        mcp_func = MCPFunction(func, name, description)
        self.functions[mcp_func.name] = mcp_func
        return mcp_func
    
    def get_function(self, name: str) -> Optional[MCPFunction]:
        """Obtém uma função pelo nome."""
        return self.functions.get(name)
    
    def get_all_functions(self) -> List[Dict[str, Any]]:
        """Retorna todas as funções registradas como esquemas JSON."""
        return [func.signature for func in self.functions.values()]
    
    async def execute_function(self, name: str, params: Dict[str, Any]) -> Any:
        """Executa uma função pelo nome com os parâmetros fornecidos."""
        func = self.get_function(name)
        if not func:
            raise ValueError(f"Função {name} não encontrada")
        
        return await func.execute(**params)
    
    async def process_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Processa uma requisição MCP."""
        function_name = request.get("function")
        params = request.get("parameters", {})
        
        if not function_name:
            return {"error": "Nome da função não fornecido"}
        
        try:
            result = await self.execute_function(function_name, params)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}