module.exports = async (req, res) => {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
  
  try {
    const response = await fetch(`${backendUrl}/api/schemes`);
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};
