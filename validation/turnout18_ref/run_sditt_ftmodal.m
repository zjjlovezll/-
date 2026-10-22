% Attempt a real SDITT FT-Modal run so stage 3 has a measured wall clock.
%
% Everything is left at the shipped settings (Type_Track = 'FT-Modal',
% Int_Method = 'Park', Vlc = 350/3.6, Type_simulation = 'Cal'): the only job of
% this driver is to time the run and record how it ended.  ASCII paths only, so
% nothing depends on the console code page.

root = 'F:\sditt_ascii';
out = 'F:\velch_tmp\sditt_wallclock.txt';

fid = fopen(out, 'w');
fprintf(fid, 'stage=starting\n');
fclose(fid);

cd(root);
t0 = tic;
status = 'ok';
msg = '';
try
    SDITT_CR400_NoStrTIrr_250728_Face
catch err
    status = 'error';
    msg = getReport(err, 'basic', 'hyperlinks', 'off');
end
wall = toc(t0);

fid = fopen(out, 'w');
fprintf(fid, 'stage=finished\n');
fprintf(fid, 'status=%s\n', status);
fprintf(fid, 'wall_seconds=%.3f\n', wall);
fprintf(fid, 'model=%s\n', version);
fprintf(fid, 'message_start\n%s\nmessage_end\n', msg);
fclose(fid);

disp(['SDITT_STATUS ' status ' WALL ' num2str(wall)]);
