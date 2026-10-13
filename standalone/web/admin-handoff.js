(async function() {
 const status = document.getElementById('status');
 const opener = window.opener;
 let homeOrigin, consuming = false;
 const fail = () => { status.textContent = 'Authorization failed. Open Pool & Spa from your signed-in Family Home administrator account.'; };
 const timer = setTimeout(() => { window.removeEventListener('message', receive); fail(); }, 60000);
 async function receive(event) {
  if (!homeOrigin || event.origin !== homeOrigin || event.source !== opener
      || event.data?.type !== 'pool-admin-ticket' || consuming) return;
  consuming = true;
  try {
   const response = await fetch('/api/admin/handoff', {method: 'POST', credentials: 'same-origin', cache: 'no-store',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ticket: event.data.ticket})});
   if (!response.ok) throw Error('Rejected');
   opener.postMessage({type: 'pool-admin-complete'}, homeOrigin);
   clearTimeout(timer); window.removeEventListener('message', receive);
   window.opener = null;
   window.location.replace('/');
  } catch { clearTimeout(timer); window.removeEventListener('message', receive); fail(); }
 }
 window.addEventListener('message', receive);
 try {
  const response = await fetch('/api/handoff/config', {credentials: 'same-origin', cache: 'no-store'});
  if (!response.ok || !opener) throw Error('Unavailable');
  const config = await response.json();
  if (typeof config.home_origin !== 'string' || !config.home_origin.startsWith('https://')) throw Error('Unavailable');
  homeOrigin = config.home_origin;
  opener.postMessage({type: 'pool-admin-ready'}, homeOrigin);
 } catch { clearTimeout(timer); window.removeEventListener('message', receive); fail(); }
})();
