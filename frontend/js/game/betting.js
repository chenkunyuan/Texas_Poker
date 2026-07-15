export function getBetPreset(fraction, pot, minRaise, maxRaise) {
    const target = Math.round(Number(pot || 0) * fraction);
    return Math.min(maxRaise, Math.max(minRaise, target));
}

export function validateRaise(amount, minRaise, maxRaise) {
    if (!Number.isFinite(amount)) return "Enter a valid raise amount.";
    if (amount < minRaise) return `Minimum raise is ${minRaise}.`;
    if (amount > maxRaise) return `Maximum raise is ${maxRaise}.`;
    return null;
}
