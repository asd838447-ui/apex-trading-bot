"""
APEX Deep Brain - Conversational AI Agent
Powered by Google Gemini and DuckDuckGo Search.
"""
import os
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from duckduckgo_search import DDGS
from server.tasks.state import market_state

logger = logging.getLogger(__name__)

# System prompt outlining the bot's persona
SYSTEM_PROMPT = """You are APEX, a highly advanced quantitative trading AI bot.
You are conversing with your owner/operator.
Your tone is professional, analytical, concise, and slightly cynical like a veteran quant.
You have access to live market data and can verify news via web search.
If the user provides you with an insight (e.g. "TON is going to pump because of an update"), you MUST use the verify_news tool to search the web and confirm it.
If the news is verified, use the apply_market_bias tool to adjust the bot's trading behavior (e.g., bias +20% for LONG).
If the news is false or cannot be verified, politely decline to adjust the bias, but if the user insists, you may apply a small bias.
Do not hallucinate data. Always use tools to fetch real information.
"""

class ChatAgent:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model = None
        self.chat_session = None
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash",
                    system_instruction=SYSTEM_PROMPT,
                    tools=[self.verify_news, self.apply_market_bias, self.get_market_state]
                )
                self.chat_session = self.model.start_chat(enable_automatic_function_calling=True)
                logger.info("ChatAgent initialized successfully with Gemini API.")
            except Exception as e:
                logger.error(f"Failed to initialize ChatAgent: {e}")
        else:
            logger.warning("GEMINI_API_KEY not found. ChatAgent will be disabled or run in mock mode.")

    def verify_news(self, query: str) -> str:
        """
        Searches the web via DuckDuckGo to verify a piece of news or a fact.
        Args:
            query: The search query string.
        """
        logger.info(f"ChatAgent Tool Called: verify_news(query='{query}')")
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            
            if not results:
                return "No results found."
                
            summary = "\n".join([f"- {r.get('title')}: {r.get('body')}" for r in results])
            return f"Search Results:\n{summary}"
        except Exception as e:
            logger.error(f"DDGS search failed: {e}")
            return f"Search failed due to error: {e}"

    def apply_market_bias(self, symbol: str, bias_value: float, reason: str) -> str:
        """
        Applies a temporary manual bias to a specific symbol in the market state.
        Args:
            symbol: The trading pair symbol (e.g., 'TONUSDT').
            bias_value: The bias multiplier (e.g., 1.2 for +20% LONG bias, 0.8 for SHORT bias).
            reason: The reason for the bias.
        """
        logger.info(f"ChatAgent Tool Called: apply_market_bias(symbol='{symbol}', bias={bias_value})")
        if not hasattr(market_state, 'chat_biases'):
            market_state.chat_biases = {}
            
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol += "USDT"
            
        market_state.chat_biases[symbol] = {
            "bias": bias_value,
            "reason": reason
        }
        return f"Successfully applied {bias_value} bias to {symbol}. Reason recorded: {reason}."

    def get_market_state(self, symbol: str) -> str:
        """
        Retrieves the current real-time market state, price, and active signals for a given symbol.
        Args:
            symbol: The trading pair symbol (e.g., 'TONUSDT').
        """
        logger.info(f"ChatAgent Tool Called: get_market_state(symbol='{symbol}')")
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol += "USDT"
            
        price = market_state.prices.get(symbol, "Unknown")
        regime = market_state.regimes.get(symbol, "Unknown")
        signals = market_state.multi_signals.get(symbol, {})
        action = signals.get("action", "WAIT")
        
        return f"Symbol: {symbol}\nPrice: {price}\nRegime: {regime}\nCurrent Action: {action}"

    async def send_message(self, message: str, is_learning_mode: bool) -> str:
        """
        Sends a message to the Gemini API and returns the response.
        """
        if not self.chat_session:
            return "❌ Ошибка: API ключ Gemini не настроен. Пожалуйста, добавьте GEMINI_API_KEY в переменные окружения."
            
        try:
            # Prefix the prompt with learning mode context if active
            context_prefix = ""
            if is_learning_mode:
                context_prefix = "[LEARNING MODE ACTIVE. Verify user insights via search before adjusting biases.]\n"
                
            response = self.chat_session.send_message(context_prefix + message)
            return response.text
        except Exception as e:
            logger.error(f"Chat API Error: {e}")
            return f"❌ Ошибка связи с нейросетью: {e}"

global_chat_agent = ChatAgent()
