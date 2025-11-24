"""
Agent Logger
Provides detailed logging and reasoning tracking for agents
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class AgentLogger:
    """Tracks detailed logs, reasoning, and progress for agents"""
    
    def __init__(self, agent_name: Optional[str] = None):
        self.agent_name = agent_name or "Unknown Agent"
        self.logs: List[Dict[str, Any]] = []
        self.progress = 0.0
        self.status = "pending"
        self._reasoning_list: List[str] = []  # Renamed to avoid shadowing the method
        self.findings: List[Dict[str, Any]] = []
        self.metrics: Dict[str, Any] = {}
    
    def log(self, agent_name: str, level: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Add a log entry"""
        self.agent_name = agent_name  # Update agent name if provided
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,  # info, warning, error, success
            "message": message,
            "data": data or {}
        }
        self.logs.append(log_entry)
        return log_entry
    
    def reasoning(self, agent_name: str, message: str):
        """Add reasoning for a decision or action"""
        self.agent_name = agent_name  # Update agent name if provided
        self._reasoning_list.append(message)  # Use renamed attribute
        self.log(agent_name, "info", f"Reasoning: {message}")
    
    def reason(self, message: str):
        """Add reasoning for a decision or action (convenience method without agent_name)"""
        self._reasoning_list.append(message)  # Use renamed attribute
        if self.agent_name:
            self.log(self.agent_name, "info", f"Reasoning: {message}")
    
    def get_agent_reasoning(self) -> List[str]:
        """Get all reasoning entries"""
        return self._reasoning_list  # Use renamed attribute
    
    def update_progress(self, progress: float, message: Optional[str] = None):
        """Update progress (0.0 to 1.0)"""
        self.progress = min(1.0, max(0.0, progress))
        if message and self.agent_name:
            self.log(self.agent_name, "info", f"Progress: {int(self.progress * 100)}% - {message}")
    
    def add_finding(self, finding: Dict[str, Any]):
        """Add a finding/issue"""
        finding["timestamp"] = datetime.now().isoformat()
        self.findings.append(finding)
        if self.agent_name:
            self.log(self.agent_name, "warning", f"Finding: {finding.get('description', 'Unknown issue')}", data=finding)
    
    def set_status(self, status: str):
        """Set agent status"""
        self.status = status
        if self.agent_name:
            self.log(self.agent_name, "success" if status == "completed" else "info", f"Status changed to: {status.upper()}")
    
    def set_metric(self, key: str, value: Any):
        """Set a metric"""
        self.metrics[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert logger state to dictionary"""
        return {
            "agent_name": self.agent_name,
            "status": self.status,
            "progress": self.progress,
            "logs": self.logs,
            "reasoning": self._reasoning_list,  # Use renamed attribute
            "findings": self.findings,
            "metrics": self.metrics,
            "summary": f"{len(self.findings)} findings, {len(self.logs)} log entries"
        }

