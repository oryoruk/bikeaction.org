import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';

import { ViolationDetailPage } from './violation-detail.page';

const routes: Routes = [
  {
    path: '',
    component: ViolationDetailPage,
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class ViolationDetailPageRoutingModule {}
