A secretary you can work with in Slack. Secretary can extract action items and todo's from text you provide it and will create Trello cards for each task. You can them ask Secretary questions about cards and have it update the card contents, due date, completion status, and all other metadata.

# Setup
## Secrets
All secrets should go in a .env file in the project's top-level directory.

### OpenAI
In the .env file you should define:
```
OPENAI_API_KEY=your_openai_api_key
```

### Slack
In the .env file you should define these [token types](https://api.slack.com/concepts/token-types):
```
SLACK_APP_TOKEN=xapp-your_slack_app_token
SLACK_BOT_TOKEN=xoxb-your_slack_bot_token
```
- Create a new slack app by going to your [slack apps page](https://api.slack.com/apps) where you will find a button/link to create a new app.
- On the App's page, find the App-Level Tokens and give your app the `[connections:write]` scope. Then you can copy the app-level token with this scope. App-level tokens start with `xapp-`.
- Once you've created the app and given it the necessary permission scope, install it in your workspace. Then you can find the bot token on the bot's Install App tab or the OAuth & Permissions tab. Bot tokens start with `xoxb-`.

### Trello
In the .env file you should define:
```
TRELLO_API_KEY=your_api_key
TRELLO_API_SECRET=your_api_secret
TRELLO_OAUTH_TOKEN=your_oauth_token
```
- [Managing API Key](https://developer.atlassian.com/cloud/trello/guides/rest-api/api-introduction/#managing-your-api-key) 
- After creating a Power Up, go to its API Key page where you will find the API Key, the API Secret, and a link to generate a user OAuth Token.

# Run the secretary
`python ./secretary/secretary_slack_bot.py`
