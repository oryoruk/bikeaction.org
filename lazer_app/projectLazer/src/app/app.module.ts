import { NgModule, isDevMode } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { RouteReuseStrategy } from '@angular/router';

import * as CordovaSQLiteDriver from 'localforage-cordovasqlitedriver';
import { IonicModule, IonicRouteStrategy } from '@ionic/angular';
import { IonicStorageModule } from '@ionic/storage-angular';
import { Drivers } from '@ionic/storage';
import { FormsModule } from '@angular/forms';
import { Storage } from '@ionic/storage-angular';

import { AppComponent } from './app.component';
import { AppRoutingModule } from './app-routing.module';
import { ServiceWorkerModule } from '@angular/service-worker';

import { RenderImagePipe } from './render-image.pipe';
import { ChooseAddressModalComponent } from './choose-address-modal/choose-address-modal.component';
import { ChooseViolationModalComponent } from './choose-violation-modal/choose-violation-modal.component';
import { ConfirmViolationDetailsModalComponent } from './confirm-violation-details-modal/confirm-violation-details-modal.component';
import { SuccessModalComponent } from './success-modal/success-modal.component';

import { TypeaheadComponent } from './components/typeahead-select.component';

@NgModule({
  declarations: [
    AppComponent,
    ChooseAddressModalComponent,
    ChooseViolationModalComponent,
    ConfirmViolationDetailsModalComponent,
    SuccessModalComponent,
    TypeaheadComponent,
  ],
  imports: [
    RenderImagePipe,
    FormsModule,
    BrowserModule,
    IonicModule.forRoot({
      hardwareBackButton: false,
      swipeBackEnabled: false,
    }),
    IonicStorageModule.forRoot({
      name: 'laserVision',
      driverOrder: [CordovaSQLiteDriver._driver, Drivers.IndexedDB],
    }),
    AppRoutingModule,
    ServiceWorkerModule.register('ngsw-worker.js', {
      enabled: !isDevMode(),
      // Register the ServiceWorker as soon as the application is stable
      // or after 30 seconds (whichever comes first).
      registrationStrategy: 'registerWhenStable:30000',
    }),
  ],
  providers: [
    { provide: RouteReuseStrategy, useClass: IonicRouteStrategy },
    Storage,
  ],
  bootstrap: [AppComponent],
})
export class AppModule {}
