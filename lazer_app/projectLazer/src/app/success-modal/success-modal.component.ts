import { Component } from '@angular/core';
import { ModalController } from '@ionic/angular';

@Component({
  selector: 'app-success-modal',
  templateUrl: './success-modal.component.html',
  styleUrls: ['./success-modal.component.scss'],
  standalone: false,
})
export class SuccessModalComponent {
  constructor(private modalCtrl: ModalController) {}

  cancel() {
    return this.modalCtrl.dismiss();
  }

  confirm() {
    this.modalCtrl.dismiss();
  }
}
