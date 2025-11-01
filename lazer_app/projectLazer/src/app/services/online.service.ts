import { Injectable } from '@angular/core';
import { Network } from '@capacitor/network';

@Injectable({
  providedIn: 'root',
})
export class OnlineStatusService {
  online: boolean | null = null;

  constructor() {
    Network.getStatus().then((connectionStatus) => {
      this.online = connectionStatus.connected;
    });
    Network.addListener('networkStatusChange', (connectionStatus) => {
      this.online = connectionStatus.connected;
    });
  }
}
