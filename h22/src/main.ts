import { PlantGrowthApp } from './App';

function init() {
  const app = new PlantGrowthApp('renderCanvas', 'uiPanel');
  app.start();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
