export const SHELLS = ['/bin/bash', '/bin/sh', '/bin/zsh', '/usr/bin/bash', '/usr/bin/zsh', '/usr/sbin/nologin', '/bin/false'];
export const USER_FIELDS = ['username', 'full_name', 'email', 'groups', 'shell'];
const linuxName = /^[a-z_][a-z0-9_-]{0,31}$/;
export function blankUser(username = '') { return {username, full_name:'', email:'', groups:'', shell:'', grant_sudo:false}; }
export function validateUserRows(rows, mode) {
  const errors = [], users = [], seen = new Set();
  if (!rows.length || rows.length > 500) errors.push('Use between 1 and 500 users per operation.');
  rows.forEach((row, index) => {
    const user = Object.fromEntries(USER_FIELDS.map(key => [key, String(row[key] || '').trim()]).filter(([,value]) => value));
    if (row.grant_sudo === true) user.grant_sudo = true;
    if (user.email) user.email = user.email.toLowerCase();
    if (!user.username && mode === 'add' && user.email) user.username = user.email.split('@')[0];
    const fail = message => errors.push(`Row ${index + 1}: ${message}`);
    if (!linuxName.test(user.username || '')) fail('Enter a valid Linux username (lowercase letters, digits, underscores, or hyphens).');
    else if (user.username === 'root') fail('The root account is protected.');
    else if (seen.has(user.username)) fail(`Duplicate username "${user.username}".`);
    seen.add(user.username);
    if (mode === 'add' && !user.full_name) fail('Full name is required.');
    if (user.full_name && (!/^[^{}<>\r\n$`|;]{1,120}$/.test(user.full_name) || /[\x00-\x1f]/.test(user.full_name))) fail('Full name contains unsupported characters or exceeds 120 characters.');
    if (user.email && !/^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$/i.test(user.email)) fail('Enter a valid email address.');
    if (user.groups) {
      user.groups = [...new Set(user.groups.split(',').map(s => s.trim()).filter(Boolean))].join(',');
      if (!user.groups || !user.groups.split(',').every(g => linuxName.test(g))) fail('Groups must be comma-separated Linux group names.');
    }
    if (user.shell && !SHELLS.includes(user.shell)) fail('Choose a supported login shell.');
    if (mode === 'edit' && !['full_name','email','groups','shell','grant_sudo'].some(key => user[key])) fail('Enter at least one change. Blank fields keep their current value.');
    users.push(user);
  });
  return {users, errors};
}
export function csvTemplate(mode) {
  return 'username,full_name,email,groups,shell,grant_sudo\n' + (mode === 'edit'
    ? 'jane,,,"developers,docker",/bin/bash,\n'
    : 'jane,Jane Example,jane@example.com,developers,/bin/bash,false\n');
}
