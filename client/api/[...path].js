/**
 * Vercel catch-all serverless proxy.
 *
 * Forwards every /api/* request from the browser to the VM API server,
 * running server-side so there is no mixed-content block.
 *
 * Request:  POST https://ref-on-record.vercel.app/api/auth/login/
 * Upstream: POST http://74.241.132.64:8080/api/auth/login/
 */

const VM_BASE = 'http://74.241.132.64:8080';

export default async function handler(req, res) {
  // req.url is e.g. /api/auth/login/ — forward it verbatim to the VM
  const upstream = `${VM_BASE}${req.url}`;

  const headers = {};
  if (req.headers.authorization)    headers['authorization']  = req.headers.authorization;
  if (req.headers['x-api-key'])     headers['x-api-key']      = req.headers['x-api-key'];

  const init = { method: req.method, headers };

  if (!['GET', 'HEAD'].includes(req.method)) {
    init.body    = JSON.stringify(req.body);
    headers['content-type'] = 'application/json';
  }

  try {
    const vmRes = await fetch(upstream, init);
    const body  = await vmRes.text();
    const ct    = vmRes.headers.get('content-type') || 'application/json';
    res.status(vmRes.status).setHeader('content-type', ct).send(body);
  } catch (err) {
    res.status(502).json({ error: 'upstream_unreachable', detail: err.message });
  }
}
