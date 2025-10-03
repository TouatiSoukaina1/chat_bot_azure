import React, { useState, useRef, useEffect } from 'react';
import { Send, Plus, Menu, User, Bot } from 'lucide-react';

export default function ChatbotInterface() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Bonjour ! Je suis votre assistant RAG. Comment puis-je vous aider aujourd\'hui ?' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    // Simulation d'une réponse (à remplacer par votre API RAG)
    setTimeout(() => {
      const assistantMessage = {
        role: 'assistant',
        content: 'Ceci est une réponse simulée. Intégrez ici votre backend RAG pour obtenir des réponses réelles basées sur vos documents.'
      };
      setMessages(prev => [...prev, assistantMessage]);
      setIsTyping(false);
    }, 1000);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const startNewChat = () => {
    setMessages([
      { role: 'assistant', content: 'Bonjour ! Je suis votre assistant RAG. Comment puis-je vous aider aujourd\'hui ?' }
    ]);
  };

  return (
    <div className="flex h-screen bg-white">
      {/* Sidebar */}
      <div className="w-64 bg-gray-50 border-r border-gray-200 flex flex-col">
        <div className="p-4">
          <button
            onClick={startNewChat}
            className="w-full flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Plus size={18} />
            <span className="text-sm font-medium">Nouvelle conversation</span>
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto px-3">
          <div className="text-xs font-semibold text-gray-500 px-3 py-2">Historique</div>
          <div className="space-y-1">
            <div className="px-3 py-2 rounded-lg hover:bg-gray-200 cursor-pointer text-sm text-gray-700">
              Conversation actuelle
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-gray-200">
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-200 cursor-pointer">
            <User size={20} className="text-gray-600" />
            <span className="text-sm text-gray-700">Mon compte</span>
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="h-14 border-b border-gray-200 flex items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Menu size={20} className="text-gray-600 cursor-pointer lg:hidden" />
            <h1 className="text-lg font-medium text-gray-800">Assistant RAG</h1>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map((message, index) => (
              <div key={index} className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center" 
                     style={{ backgroundColor: message.role === 'user' ? '#e5e7eb' : '#f3f4f6' }}>
                  {message.role === 'user' ? (
                    <User size={18} className="text-gray-600" />
                  ) : (
                    <Bot size={18} className="text-gray-700" />
                  )}
                </div>
                <div className="flex-1 pt-1">
                  <div className="text-sm font-medium text-gray-900 mb-1">
                    {message.role === 'user' ? 'Vous' : 'Assistant'}
                  </div>
                  <div className="text-gray-800 whitespace-pre-wrap leading-relaxed">
                    {message.content}
                  </div>
                </div>
              </div>
            ))}
            
            {isTyping && (
              <div className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                  <Bot size={18} className="text-gray-700" />
                </div>
                <div className="flex-1 pt-1">
                  <div className="text-sm font-medium text-gray-900 mb-1">Assistant</div>
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 p-4 bg-white">
          <div className="max-w-3xl mx-auto">
            <div className="relative flex items-end gap-2 bg-white border border-gray-300 rounded-2xl shadow-sm focus-within:border-gray-400 transition-colors">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Posez votre question..."
                className="flex-1 px-4 py-3 bg-transparent outline-none resize-none max-h-32"
                rows="1"
                style={{ minHeight: '44px' }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="m-1.5 p-2 rounded-lg bg-black text-white disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-gray-800 transition-colors"
              >
                <Send size={18} />
              </button>
            </div>
            <div className="text-xs text-gray-500 text-center mt-2">
              Interface de chatbot RAG - Connectez votre backend pour des réponses réelles
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}