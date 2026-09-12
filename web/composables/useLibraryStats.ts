export function useLibraryStats() {
  const downloadCount = useState<number>('library-download-count', () => 0)

  function setDownloadCount(count: number) {
    downloadCount.value = Math.max(0, count)
  }

  return { downloadCount, setDownloadCount }
}
