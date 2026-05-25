let state = {
  slots: {
    physical: null,
    social: new Map(),
  },
};

function getSlot(slotName) {
  if (slotName === 'social') return state.slots.social;
  return state.slots.physical;
}

function startAction(id, type, data, slot) {
  const entry = { id, type, data, status: 'running', startTime: Date.now() };

  if (slot === 'social') {
    state.slots.social.set(id, entry);
  } else {
    if (state.slots.physical && state.slots.physical.status === 'running') {
      return { cancelled: true, previousId: state.slots.physical.id };
    }
    state.slots.physical = entry;
  }

  return { cancelled: false, entry };
}

function updateState(id, status, signal, error, data, slot) {
  let entry = null;
  if (slot === 'social') {
    entry = state.slots.social.get(id);
  } else {
    entry = state.slots.physical;
  }

  if (!entry) return null;

  entry.status = status;
  if (signal) entry.endSignal = signal;
  if (error) entry.error = error;
  if (data) entry.data = data;

  return entry;
}

function completeAction(id, signal, observation, slot) {
  const entry = updateState(id, 'completed', signal, null, null, slot);
  if (!entry) return null;

  if (slot === 'social') {
    state.slots.social.delete(id);
  }
  return entry;
}

function failAction(id, error, slot) {
  const entry = updateState(id, 'failed', null, error, null, slot);
  if (slot === 'social') {
    state.slots.social.delete(id);
  }
  return entry;
}

function cancelSlot(slotName) {
  if (slotName === 'social') {
    state.slots.social.clear();
  } else {
    state.slots.physical = null;
  }
}

function stopCurrentAction(reason) {
  if (state.slots.physical && state.slots.physical.status === 'running') {
    state.slots.physical.status = 'failed';
    state.slots.physical.error = reason;
    state.slots.physical.endSignal = 'Interrupted';
  }
  state.slots.social.clear();
}

function getState() {
  return {
    physical: state.slots.physical,
    social: Array.from(state.slots.social.values()),
    isBusy: state.slots.physical !== null && state.slots.physical.status === 'running',
  };
}

function reset() {
  state = { slots: { physical: null, social: new Map() } };
}

module.exports = {
  startAction, updateState, completeAction, failAction,
  cancelSlot, stopCurrentAction, getState, reset,
};
