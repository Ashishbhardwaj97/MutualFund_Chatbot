module.exports = async (req, res) => {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
  
  if (req.method === 'POST') {
    try {
      const response = await fetch(`${backendUrl}/api/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: typeof req.body === 'string' ? req.body : JSON.stringify(req.body),
      });
      const data = await response.json();
      res.status(response.status).json(data);
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
};
