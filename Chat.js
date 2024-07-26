import React, { useState, useEffect } from 'react';
import { Box, Paper, TextField, Typography, Button, List, ListItem, ListItemText, Avatar } from '@mui/material';
import './Chat.css';

const Chat = () => {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [domain, setDomain] = useState('');

  useEffect(() => {
    // Request the current tab URL from the background script
    chrome.runtime.sendMessage({ type: 'get_current_tab_url' }, (response) => {
      if (response && response.url) {
        const url = new URL(response.url);
        setDomain(url.hostname);
      }
    });
}, []);

  const askQuestion = async () => {
    const userMessage = { text: question, user: true };
    setMessages((prevMessages) => [...prevMessages, userMessage]);
    setQuestion('');
    try {
      const res = await fetch('/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: userMessage.text, domain: domain }),
      });
      if (res.ok) {
        const data = await res.json();
        console.log('Response from backend:', data);
        const botMessage = { text: data.response, user: false };
        setMessages((prevMessages) => [...prevMessages, botMessage]);
      } else {
        const errorData = await res.json();
        const botMessage = { text: `Error: ${errorData.message}`, user: false };
        setMessages((prevMessages) => [...prevMessages, botMessage]);
      }
  } catch (error) {
    const botMessage = { text: `Error: ${error.message}`, user: false };
    setMessages((prevMessages) => [...prevMessages, botMessage]);
  }
};

return (
  <Paper className="chat-container">
    <Box className="chat-header">
      <Typography variant="h4" align="center">
        Chat
      </Typography>
    </Box>
    <Box className="chat-messages">
      <List>
        {messages.map((msg, index) => (
          <ListItem key={index} className={msg.user ? 'user-message' : 'bot-message'}>
            <Avatar className="avatar" />
            <ListItemText primary={msg.text} />
          </ListItem>
        ))}
      </List>
    </Box>
    <Box className="chat-input">
      <TextField
        id="outlined-basic"
        label="Ask a question"
        variant="outlined"
        fullWidth
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        multiline
        rows={2}
        sx={{ marginBottom: 2 }}
      />
      <Button variant="contained" onClick={askQuestion} sx={{ marginBottom: 2 }}>
        Ask
      </Button>
    </Box>
  </Paper>
 );
};

export default Chat;
