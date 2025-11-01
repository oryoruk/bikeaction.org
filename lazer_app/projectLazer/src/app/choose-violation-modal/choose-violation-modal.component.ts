import { Component, Input } from '@angular/core';
import { ModalController } from '@ionic/angular';

import { get_options } from '../violation-matcher/violation-matcher';

const iconMap = new Map([
  [
    'Bike Lane (vehicle parked in bike lane)',
    'assets/icons/noun-bike-lane-19256.svg',
  ],
  [
    'Handicap Ramp (vehicle blocking handicap ramp)',
    'assets/icons/noun-handicap-3217991.svg',
  ],
  [
    'Crosswalk (vehicle on crosswalk)',
    'assets/icons/noun-crosswalk-7075103.svg',
  ],
  ['Sidewalk', 'assets/icons/noun-bad-parking-470749.svg'],
  [
    'Corner Clearance (vehicle parked on corner)',
    'assets/icons/noun-intersection-6096494.svg',
  ],
]);

@Component({
  selector: 'app-choose-violation-modal',
  templateUrl: './choose-violation-modal.component.html',
  styleUrls: ['./choose-violation-modal.component.scss'],
  standalone: false,
})
export class ChooseViolationModalComponent {
  selection!: string;
  violations: string[] = get_options('Violation Observed') as string[];

  constructor(private modalCtrl: ModalController) {}

  renderViolationText(violation: string): string {
    if (violation.split('(').length > 1) {
      return `<div style="display: flex; flex-direction: column;"><div>${
        violation.split('(')[0]
      }</div><div><small>(${violation.split('(')[1]}</small></div>`;
    } else {
      return `<div>${violation}</div>`;
    }
  }
  getViolationIcon(violation: string): string | null {
    const icon = iconMap.get(violation) || null;
    return icon;
  }

  setViolation(violation: string) {
    this.selection = violation;
    this.modalCtrl.dismiss(this.selection, 'save');
  }

  back() {
    return this.modalCtrl.dismiss(null, 'back');
  }

  cancel() {
    return this.modalCtrl.dismiss({ note: null }, 'cancel');
  }

  confirm() {
    this.modalCtrl.dismiss(this.selection, 'save');
  }
}
