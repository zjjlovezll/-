% Inspect the SDITT flexible-track matrix file without loading it.
% Mat_FT_S8b.mat is ~984 MB, so `whos -file` first and only then decide what to load.
root = 'G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728';
file = fullfile(root, 'Mat_FT_S8b.mat');

fprintf('=== whos -file Mat_FT_S8b.mat ===\n');
listing = whos('-file', file);
for k = 1:numel(listing)
    entry = listing(k);
    fprintf('%-28s %-12s %s\n', entry.name, entry.class, mat2str(entry.size));
end

fprintf('\n=== probing a few variables ===\n');
info = whos('-file', file);
names = {info.name};
for k = 1:numel(names)
    name = names{k};
    if any(strcmp(name, {'M_track', 'K_track', 'C_track', 'Phi', 'ModeShape', 'freq', 'omega'}))
        fprintf('loading %s ...\n', name);
        data = load(file, name);
        value = data.(name);
        if issparse(value)
            fprintf('  %s: sparse %s, nnz = %d\n', name, mat2str(size(value)), nnz(value));
        else
            fprintf('  %s: %s %s, class %s\n', name, mat2str(size(value)), ...
                    mat2str(size(value, 1)), class(value));
        end
        clear data value
    end
end
fprintf('done\n');
