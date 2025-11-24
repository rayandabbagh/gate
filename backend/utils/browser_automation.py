"""
Browser Automation Utility
Uses Playwright for real browser automation - actual clicks, forms, navigation
"""

import asyncio
from typing import Dict, List, Any, Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class BrowserAutomation:
    """Real browser automation using Playwright"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
    
    async def initialize(self):
        """Initialize Playwright browser"""
        try:
            self.playwright = await async_playwright().start()
            # Use chromium for headless automation
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            return True
        except Exception as e:
            print(f"Error initializing browser: {str(e)}")
            return False
    
    async def close(self):
        """Close browser"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
    
    async def execute_flow(
        self, 
        flow: Dict[str, Any], 
        base_url: str = "http://localhost:3000"
    ) -> Dict[str, Any]:
        """
        Execute a user flow in real browser
        
        Flow format:
        {
            "name": "User Signup Flow",
            "steps": [
                {"type": "navigate", "url": "/"},
                {"type": "click", "selector": "button.signup"},
                {"type": "fill", "selector": "input[name='email']", "value": "test@example.com"},
                {"type": "fill", "selector": "input[name='password']", "value": "password123"},
                {"type": "click", "selector": "button[type='submit']"},
                {"type": "wait", "selector": ".welcome-message"},
                {"type": "assert", "selector": ".welcome-message", "contains": "Welcome"}
            ]
        }
        """
        if not self.page:
            if not await self.initialize():
                return {
                    "flow_name": flow.get("name", "unknown"),
                    "status": "failed",
                    "error": "Failed to initialize browser",
                    "steps_completed": 0
                }
        
        flow_name = flow.get("name", "unknown")
        steps = flow.get("steps", [])
        execution_logs = []
        errors = []
        
        try:
            for idx, step in enumerate(steps):
                step_num = idx + 1
                step_type = step.get("type", "unknown")
                
                execution_logs.append({
                    "step": step_num,
                    "type": step_type,
                    "status": "pending"
                })
                
                try:
                    if step_type == "navigate":
                        url = step.get("url", "/")
                        full_url = f"{base_url}{url}" if not url.startswith("http") else url
                        await self.page.goto(full_url, wait_until="domcontentloaded", timeout=10000)
                        execution_logs[-1]["status"] = "success"
                    
                    elif step_type == "click":
                        selector = step.get("selector")
                        await self.page.click(selector, timeout=5000)
                        execution_logs[-1]["status"] = "success"
                    
                    elif step_type == "fill":
                        selector = step.get("selector")
                        value = step.get("value", "")
                        await self.page.fill(selector, value, timeout=5000)
                        execution_logs[-1]["status"] = "success"
                    
                    elif step_type == "wait":
                        selector = step.get("selector")
                        timeout = step.get("timeout", 5000)
                        await self.page.wait_for_selector(selector, timeout=timeout)
                        execution_logs[-1]["status"] = "success"
                    
                    elif step_type == "assert":
                        selector = step.get("selector")
                        expected = step.get("contains") or step.get("text") or step.get("visible", True)
                        
                        if step.get("contains"):
                            text = await self.page.text_content(selector)
                            if expected not in (text or ""):
                                raise AssertionError(f"Expected '{expected}' in text, got '{text}'")
                        elif step.get("visible"):
                            element = await self.page.query_selector(selector)
                            if not element:
                                raise AssertionError(f"Element {selector} not found")
                        
                        execution_logs[-1]["status"] = "success"
                    
                    elif step_type == "scroll":
                        selector = step.get("selector")
                        if selector:
                            await self.page.evaluate(f"document.querySelector('{selector}').scrollIntoView()")
                        else:
                            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        execution_logs[-1]["status"] = "success"
                    
                    else:
                        execution_logs[-1]["status"] = "skipped"
                        execution_logs[-1]["error"] = f"Unknown step type: {step_type}"
                
                except Exception as e:
                    error_msg = f"Step {step_num} ({step_type}) failed: {str(e)}"
                    errors.append(error_msg)
                    execution_logs[-1]["status"] = "failed"
                    execution_logs[-1]["error"] = str(e)
                    
                    # Stop flow on critical failure
                    if step.get("critical", False):
                        break
            
            # Determine overall status
            failed_steps = [s for s in execution_logs if s.get("status") == "failed"]
            status = "success" if len(failed_steps) == 0 else "failed"
            
            return {
                "flow_name": flow_name,
                "status": status,
                "steps_completed": len([s for s in execution_logs if s.get("status") == "success"]),
                "total_steps": len(steps),
                "execution_logs": execution_logs,
                "errors": errors
            }
        
        except Exception as e:
            return {
                "flow_name": flow_name,
                "status": "failed",
                "error": f"Flow execution error: {str(e)}",
                "steps_completed": len([s for s in execution_logs if s.get("status") == "success"]),
                "total_steps": len(steps),
                "execution_logs": execution_logs,
                "errors": errors + [str(e)]
            }
    
    async def convert_string_flow_to_steps(
        self, 
        flow_string: str, 
        base_url: str = "http://localhost:3000"
    ) -> List[Dict[str, Any]]:
        """
        Convert string-based flow description to executable steps
        
        Example: "Navigate to /, Click signup button, Fill email form, Submit"
        """
        steps = []
        
        # Simple pattern matching to convert text to actions
        flow_lower = flow_string.lower()
        
        if "navigate" in flow_lower or "go to" in flow_lower or "visit" in flow_lower:
            # Extract URL
            import re
            url_match = re.search(r'/(?:[^\s,]+|["\']([^"\']+)["\'])', flow_string)
            url = url_match.group(1) if url_match and url_match.group(1) else "/"
            steps.append({"type": "navigate", "url": url})
        
        if "click" in flow_lower:
            # Extract selector
            import re
            button_match = re.search(r'click\s+([^\s,]+)', flow_lower)
            if button_match:
                selector_text = button_match.group(1)
                # Convert common text to selectors
                selector = self._text_to_selector(selector_text)
                steps.append({"type": "click", "selector": selector})
        
        if "fill" in flow_lower or "enter" in flow_lower:
            # Extract form field
            import re
            field_match = re.search(r'(fill|enter)\s+([^\s,]+)', flow_lower)
            if field_match:
                field_text = field_match.group(2)
                selector = self._text_to_selector(field_text)
                steps.append({"type": "fill", "selector": selector, "value": "test@example.com"})
        
        if "submit" in flow_lower:
            steps.append({"type": "click", "selector": "button[type='submit']"})
        
        if "wait" in flow_lower:
            # Extract what to wait for
            import re
            wait_match = re.search(r'wait\s+for\s+([^\s,]+)', flow_lower)
            if wait_match:
                selector_text = wait_match.group(1)
                selector = self._text_to_selector(selector_text)
                steps.append({"type": "wait", "selector": selector})
        
        return steps
    
    def _text_to_selector(self, text: str) -> str:
        """Convert human-readable text to CSS selector"""
        text = text.lower().strip()
        
        # Common patterns
        if "button" in text:
            if "signup" in text or "sign up" in text:
                return "button.signup, .signup-button, [data-testid='signup']"
            elif "login" in text or "log in" in text:
                return "button.login, .login-button, [data-testid='login']"
            elif "submit" in text:
                return "button[type='submit']"
            else:
                return f"button:has-text('{text}')"
        
        if "email" in text:
            return "input[name='email'], input[type='email']"
        
        if "password" in text:
            return "input[name='password'], input[type='password']"
        
        # Default: try as class or data attribute
        return f".{text.replace(' ', '-')}, [data-testid='{text.replace(' ', '-')}']"

