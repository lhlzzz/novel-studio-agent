module.exports = {
  apps: [
    {
      name: 'xiaoping-cdp',
      script: '/root/.local/bin/hermes-cdp',
      args: 'xiaoping',
      cwd: __dirname,
      interpreter: 'none',
      autorestart: true,
      max_restarts: 3,
      restart_delay: 5000,
      env: {
        HERMES_PROJECT: 'xiaoping',
      },
    },
  ],
};
