import assert from 'node:assert/strict';
import test from 'node:test';
import { compileView, element, find, renderer, text } from '../../test-support/vue.js';

const { default: InspectionResults } = await import(await compileView(new URL('./InspectionResults.vue', import.meta.url)));

test('readiness reports expose findings and missing evidence per device', () => {
  const clear = { status: 'ok', detail: 'Within threshold.' };
  const checks = { root_capacity: clear, memory: clear, services: clear, reboot: clear };
  const reports = [
    { report_type: 'host_readiness', hostname: 'alpha', checks: {
      ...checks, future_extension: null,
      memory: { status: 'attention', detail: '4% available.', advice: 'Review workloads first.' },
      services: { status: 'unavailable', detail: 'Service manager unavailable.' },
    } },
    { report_type: 'host_readiness', hostname: 'bravo', checks: {
      ...checks, reboot: { status: 'not_applicable', detail: 'Debian marker only.' },
    } },
  ];
  const root = element('root');
  const app = renderer.createApp(InspectionResults, { reports, devices: [{ inventory_name: 'alpha', name: 'Alpha node' }] });
  try {
    app.mount(root);
    const alpha = find(root, n => n.tag === 'details' && text(n).includes('Alpha node'));
    const bravo = find(root, n => n.tag === 'details' && text(n).includes('bravo'));
    assert.equal(alpha.props.open, true);
    assert.equal(bravo.props.open, false);
    assert.match(text(alpha), /1 finding to review · 1 check unavailable/);
    assert.match(text(alpha), /4% available\.Review workloads first\./);
    assert.match(text(bravo), /No findings in applicable checks/);
    assert.match(text(bravo), /Not applicable/);
  } finally {
    app.unmount();
  }
});
