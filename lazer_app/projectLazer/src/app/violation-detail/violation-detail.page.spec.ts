import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ViolationDetailPage } from './violation-detail.page';

describe('ViolationDetailPage', () => {
  let component: ViolationDetailPage;
  let fixture: ComponentFixture<ViolationDetailPage>;

  beforeEach(() => {
    fixture = TestBed.createComponent(ViolationDetailPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
