// Offline integrity check; upstream freshness/adoption is a separate review gate.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';

const sourcePath='docs/canonworks/reviewer-standards.md';
const document=readFileSync(sourcePath);
const version=document.toString().match(/\*\*(CW-RS-\d+\.\d+) · Draft ·/)?.[1];
if (!version) throw new Error('Reviewer standards need an explicit draft version.');
if (process.argv.includes('--canonical')) {
  console.log(`Canonical reviewer standards ${version} readable.`);
} else {
  const pin=JSON.parse(readFileSync('docs/canonworks/reviewer-standards-source.json','utf8'));
  if (pin.repository!=='https://github.com/brock-run/canon-flow' ||
      pin.path!==sourcePath || !/^[a-f0-9]{40}$/.test(pin.revision) ||
      pin.version!==version || pin.sha256!==createHash('sha256').update(document).digest('hex')) {
    throw new Error('Reviewer snapshot/provenance mismatch. Regenerate from its CanonFlow source.');
  }
  console.log(`Reviewer snapshot ${version} verified at ${pin.revision}. Freshness/adoption not inferred.`);
}
