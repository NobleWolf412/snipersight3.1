const {defineConfig} = require('@playwright/test');
const path = require('path');
module.exports=defineConfig({
  testDir:'./tests',testMatch:'cockpit.spec.cjs',
  outputDir:'../artifacts/browser-results',fullyParallel:false,workers:1,
  use:{baseURL:'http://127.0.0.1:8437',trace:'retain-on-failure'},
  projects:[
    {name:'desktop-chromium',use:{browserName:'chromium',viewport:{width:1440,height:1000}}},
    {name:'phone-webkit',use:{browserName:'webkit',viewport:{width:390,height:844},isMobile:true,hasTouch:true}},
  ],
  // A fixed scratch-only harness; never reuse the production server.
  webServer:{command:process.platform==='win32'?`"${path.resolve(__dirname,'../.venv/Scripts/python.exe')}" tests/cockpit_preview.py`:'python tests/cockpit_preview.py',
    url:'http://127.0.0.1:8437/api/ui/v1/context',reuseExistingServer:true,timeout:30000},
});
