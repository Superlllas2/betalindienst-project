(function () {
  function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex += 1;
    }
    return `${size.toFixed(size < 10 && unitIndex > 0 ? 1 : 0)} ${units[unitIndex]}`;
  }

  function formatNumber(value) {
    if (value === null || value === undefined) {
      return '—';
    }
    if (typeof value === 'number') {
      return value.toLocaleString();
    }
    return String(value);
  }

  window.AppUtils = {
    formatBytes,
    formatNumber,
  };
})();
