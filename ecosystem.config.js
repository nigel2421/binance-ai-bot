module.exports = {
  apps: [
    {
      name: 'deriv-crypto-ai-bot',
      script: 'main.py',
      args: '--paper 3600',
      interpreter: 'python',
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      restart_delay: 5000,
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
      },
    },
  ],
};
