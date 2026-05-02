const { IgApiClient } = require('instagram-private-api');
const fs = require('fs');

(async () => {
  const ig = new IgApiClient();

  const username = 'manofox_official';
  const password = 'YOUR_PASSWORD';

  ig.state.generateDevice(username);

  await ig.account.login(username, password);

  const state = await ig.state.serialize();
  delete state.constants;

  fs.writeFileSync(
    `session_${username}.json`,
    JSON.stringify(state, null, 2)
  );

  console.log('✅ Session saved');
})();