const dialog = document.querySelector('dialog[open]');
if (dialog && typeof dialog.showModal === 'function') {
  dialog.close();
  dialog.showModal();
  dialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    window.location.assign(dialog.dataset.returnUrl);
  });
}

const notice = document.querySelector('#toast');
if (notice) {
  setTimeout(() => { notice.hidden = true; }, 6500);
}
