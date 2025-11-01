import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { IonicModule } from '@ionic/angular';

import { ViolationDetailPageRoutingModule } from './violation-detail-routing.module';

import { RenderImagePipe } from '../render-image.pipe';
import { ViolationDetailPage } from './violation-detail.page';

@NgModule({
  imports: [
    CommonModule,
    FormsModule,
    IonicModule,
    ViolationDetailPageRoutingModule,
    RenderImagePipe,
  ],
  declarations: [ViolationDetailPage],
})
export class ViolationDetailPageModule {}
