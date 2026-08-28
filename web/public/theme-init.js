(function () {
  try {
    var key = 'video-cortes-theme'
    var theme = localStorage.getItem(key)
    if (theme !== 'dark' && theme !== 'light') theme = 'light'
    document.documentElement.setAttribute('data-theme', theme)
    document.documentElement.style.colorScheme = theme
  } catch (e) {}
})()
