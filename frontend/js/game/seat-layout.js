const PLAYER_POSITIONS = {
    2: [
        { x: 50, y: 86 },
        { x: 50, y: 20 },
    ],
    3: [
        { x: 50, y: 86 },
        { x: 15, y: 25 },
        { x: 85, y: 25 },
    ],
    4: [
        { x: 50, y: 86 },
        { x: 10, y: 30 },
        { x: 90, y: 30 },
        { x: 50, y: 18 },
    ],
    5: [
        { x: 50, y: 86 },
        { x: 8, y: 35 },
        { x: 92, y: 35 },
        { x: 30, y: 16 },
        { x: 70, y: 16 },
    ],
    6: [
        { x: 50, y: 86 },
        { x: 5, y: 35 },
        { x: 95, y: 35 },
        { x: 20, y: 14 },
        { x: 80, y: 14 },
        { x: 50, y: 14 },
    ],
    7: [
        { x: 50, y: 86 },
        { x: 5, y: 35 },
        { x: 95, y: 35 },
        { x: 12, y: 14 },
        { x: 88, y: 14 },
        { x: 35, y: 10 },
        { x: 65, y: 10 },
    ],
    8: [
        { x: 50, y: 86 },
        { x: 5, y: 35 },
        { x: 95, y: 35 },
        { x: 8, y: 14 },
        { x: 92, y: 14 },
        { x: 25, y: 9 },
        { x: 75, y: 9 },
        { x: 50, y: 9 },
    ],
    9: [
        { x: 50, y: 86 },
        { x: 5, y: 38 },
        { x: 95, y: 38 },
        { x: 7, y: 16 },
        { x: 93, y: 16 },
        { x: 18, y: 8 },
        { x: 82, y: 8 },
        { x: 38, y: 7 },
        { x: 62, y: 7 },
    ],
};

export function getSeatPositions(count) {
    if (PLAYER_POSITIONS[count]) return PLAYER_POSITIONS[count].map((position) => ({ ...position }));
    if (count < 2) return [];
    const positions = [{ x: 50, y: 86 }];
    for (let index = 0; index < count - 1; index += 1) {
        const fraction = (index + 1) / count;
        positions.push({
            x: Math.round(5 + fraction * 90),
            y: Math.round(14 + Math.sin(fraction * Math.PI) * 24),
        });
    }
    return positions;
}
